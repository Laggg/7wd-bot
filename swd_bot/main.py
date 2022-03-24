import pickle
from pathlib import Path
from typing import List, Callable, Optional

import pandas as pd
import pyglet
import torch
from swd.action import BuyCardAction, DiscardCardAction, BuildWonderAction
from swd.agents import Agent, RecordedAgent, ConsoleAgent, RandomAgent
from swd.entity_manager import EntityManager
from swd.game import Game
from swd.states.game_state import GameState
from tqdm import tqdm

from swd_bot.agents.mcts_agent import MCTSAgent
from swd_bot.agents.torch_agent import TorchAgent
from swd_bot.data_providers.feature_extractor import FlattenEmbeddingsFeatureExtractor
from swd_bot.data_providers.torch_data_provider import TorchDataset
from swd_bot.game_features import GameFeatures
from swd_bot.game_view import GameWindow
from swd_bot.model.torch_models import TorchBaseline, TorchBaselineEmbeddings
from swd_bot.sevenee import SeveneeLoader
from swd_bot.state_features import StateFeatures
from swd_bot.swdio import SwdioLoader


def generate_words():
    words = []
    for path in tqdm(list(Path("../../7wd/sevenee").rglob("*.json"))):
        state, agents = SeveneeLoader.load(path)
        if state is None:
            continue
        game_features = GameFeatures(state, agents)
        for age, age_state in enumerate(game_features.age_states):
            for player in range(2):
                d = {
                    "path": str(path),
                    "age": age,
                    "player": player,
                    "words": "_".join(map(str, age_state.players_state[player].cards))
                }
                words.append(d)
    df = pd.DataFrame(words)
    df.to_csv("words.csv", index=False)


def process_sevenee_games(process_function: Callable[[GameState, List[Agent]], None]):
    for file in Path(f"../../7wd/sevenee/").rglob("*.json"):
        state, agents = SeveneeLoader.load(file)
        if state is None:
            continue
        print(file)
        process_function(state, agents)


def collect_states_actions():
    saved_states = [[], [], []]
    saved_actions = [[], [], []]

    def save_state(state: GameState, agents: List[Agent]):
        while not Game.is_finished(state):
            actions = Game.get_available_actions(state)
            if Game.is_finished(state):
                break
            agent = agents[state.current_player_index]
            selected_action = agent.choose_action(state, actions)
            if isinstance(selected_action, BuyCardAction) or isinstance(selected_action, DiscardCardAction) \
                    or isinstance(selected_action, BuildWonderAction):
                index = 0
                if state.meta_info["season"] % 5 == 0:
                    index = 2
                elif state.meta_info["season"] % 5 == 4:
                    index = 1
                saved_states[index].append(state.clone())
                saved_actions[index].append(selected_action)

            Game.apply_action(state, selected_action)

    process_sevenee_games(save_state)

    suffixes = ["_train", "_valid", "_test"]
    for i in range(3):
        with open(f"../datasets/buy_discard_build/states{suffixes[i]}.pkl", "wb") as f:
            pickle.dump(saved_states[i], f)

        with open(f"../datasets/buy_discard_build/actions{suffixes[i]}.pkl", "wb") as f:
            pickle.dump(saved_actions[i], f)


def collect_games_features():
    games_features = []

    def save_features(state: GameState, agents: List[Agent]):
        recorded_agents: List[RecordedAgent] = []
        for agent in agents:
            if isinstance(agent, RecordedAgent):
                recorded_agents.append(agent)
        features = GameFeatures(state, recorded_agents)
        games_features.append({
            "double_turns_0": features.double_turns[0],
            "double_turns_1": features.double_turns[1],
            "first_picked_wonder": features.first_picked_wonders,
            "winner": features.winner,
            "victory": features.victory,
            "division": features.division,
            "path": features.path,
            "players": features.players
        })

    process_sevenee_games(save_features)
    df = pd.DataFrame(games_features)
    df.to_csv("../notebooks/features.csv", index=False)


def test_model():
    model = TorchBaseline(1104, 0)
    model.load_state_dict(torch.load("../models/model_flat_emb_acc48.5.pth"))
    model.eval()

    file = Path(f"../../7wd/sevenee/46/1/1/aRT22RJpJAGP8iPNs.json")
    # file = Path(f"../../7wd/sevenee/46/1/1/SuJYYgWE7fMFS8Dfi.json")
    state, agents = SeveneeLoader.load(file)
    print(state.meta_info["player_names"])
    correct = 0
    all = 0
    while not Game.is_finished(state):
        actions = Game.get_available_actions(state)
        if Game.is_finished(state):
            break
        agent = agents[state.current_player_index]
        selected_action = agent.choose_action(state, actions)

        if len(state.wonders) == 0:
            extractor = FlattenEmbeddingsFeatureExtractor()
            features, cards = extractor.features(state)
            features = torch.tensor(features, dtype=torch.float)
            cards = torch.tensor(cards, dtype=torch.float)
            action, winner = model(features[None], cards[None])
            if isinstance(selected_action, BuyCardAction) or isinstance(selected_action, DiscardCardAction)\
                    or isinstance(selected_action, BuildWonderAction):
                if action[0].argmax().item() == selected_action.card_id:
                    correct += 1
                all += 1
            print(round(winner[0][0].item(), 2), round(winner[0][1].item(), 2))

        Game.apply_action(state, selected_action)
    print(correct / all)


def play_against_ai(state: GameState):
    agents = [ConsoleAgent(), MCTSAgent(state)]
    while not Game.is_finished(state):
        actions = Game.get_available_actions(state)
        print(Game.print(state))
        agent = agents[state.current_player_index]
        selected_action = agent.choose_action(state, actions)
        Game.apply_action(state, selected_action)
        for agent in agents:
            agent.on_action_applied(selected_action, state)


def test_game(state: GameState, agents: List[Agent], verbose: bool = False):
    if verbose:
        print(state.meta_info["player_names"])

    while not Game.is_finished(state):
        print(state)
        actions = Game.get_available_actions(state)
        if Game.is_finished(state):
            break
        agent = agents[state.current_player_index]
        selected_action = agent.choose_action(state, actions)
        Game.apply_action(state, selected_action)

    for i, agent in enumerate(agents):
        if isinstance(agent, RecordedAgent):
            assert len(agent.actions) == 0
        else:
            assert False
        if "players" in state.meta_info:
            if verbose:
                print(state.players_state[i].coins, state.meta_info["players"][i]["coins"])
            assert state.players_state[i].coins == state.meta_info["players"][i]["coins"]

    if "result" in state.meta_info:
        if state.meta_info["result"]["victory"] != "tie" and state.winner != state.meta_info["result"]["winnerIndex"]:
            print(f"Winner: {state.winner}")
            print(Game.points(state, 0), Game.points(state, 1))
            print(state.meta_info["result"])
        if state.meta_info["result"]["victory"] == "tie":
            assert state.winner == -1
        else:
            assert state.winner == state.meta_info["result"]["winnerIndex"]


def extract_state(state: GameState, agents: List[Agent], stop_condition: Callable[[GameState], bool]) -> Optional[GameState]:
    while not Game.is_finished(state):
        if stop_condition(state):
            return state
        actions = Game.get_available_actions(state)
        selected_action = agents[state.current_player_index].choose_action(state, actions)
        Game.apply_action(state, selected_action)


def main():
    # with open("../notebooks/states.pkl", "rb") as f:
    #     states = pickle.load(f)
    # state: GameState = states[0]
    # print(StateFeatures.extract_state_features_dict(state))
    # print(EntityManager.card(0).bonuses)
    # collect_states_actions()
    # collect_games_features()
    # test_model()
    # play_against_ai()
    state = Game.create()
    window = GameWindow(state, [ConsoleAgent(), MCTSAgent(state)])
    pyglet.app.run()
    # state, agents = SwdioLoader.load(Path("../../7wd/7wdio/log.json"))
    # test_game(state, agents, False)

    # state, agents = SeveneeLoader.load(Path("../../7wd/sevenee/44/1/1/EJGt5TaWTXd7napf4.json"))
    # print(state.meta_info["player_names"])
    #
    # def f(s: GameState):
    #     return "PickStartPlayerAction(player_index=0)" in map(str, Game.get_available_actions(s))
    # state = extract_state(state, agents, f)
    # play_against_ai(Game.create())


if __name__ == "__main__":
    main()
