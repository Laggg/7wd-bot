## RL agent for board card game «7 Wonders: Duel»

We present our bot (based on reinforcement learning algorithms) for board card game «7 Wonders: Duel» embedded in this [online platform](https://7wd.io/welcome).
Our approach is similar to the [DeepMind's AlphaGo solution](https://www.deepmind.com/publications/mastering-the-game-of-go-with-deep-neural-networks-tree-search):
we use Monte Carlo Tree Search (MCTS) with Behavior Cloning (BC) finishers. For building tree search graph we use [7wd-engine](https://github.com/dfomin/7wd-engine) (was created by [@dfomin](https://github.com/dfomin)). Game finisher model was trained in supervised mode on ~7000 games of real players ([data_link1](https://drive.google.com/file/d/1qi3QEYamKcGypw0HPhwI5L0mwHWHR6EP/view?usp=sharing), [data_link2](https://drive.google.com/file/d/1b0mVKbzh60L3hjPX0lvt-n03IyphTquI/view?usp=sharing)).

![](demo/7wd_1.png)

### Game finisher

Game finisher is a policy model, which can choose action in some game state: **Action = model(State)**.

Posible Action - each received card can be:
- built
- discarded for coins
- used to create a world wonder
 
State consist of:
- the strength of each of the players (resources, army, science etc.)
- information about spreaded cards, each card has embedding vector
- card embedding consists of semantic and informational part (semantic part depends on other builded cards - similar to word2vec)
- type of spreaded cards: open-availabled card, open-unavailabled card, closed card, builded card.

Model consis of:
- linear layers
- relu activations

![](demo/7wd_2.png)


## Additional requirements (Python 3.9+ is supported)

- Clone https://github.com/dfomin/7wd-engine
- Add 7wd-engine to PYTHONPATH or add the path to jupyter notebook
- Dowland data for BC [data_link1](https://drive.google.com/file/d/1qi3QEYamKcGypw0HPhwI5L0mwHWHR6EP/view?usp=sharing), [data_link2](https://drive.google.com/file/d/1b0mVKbzh60L3hjPX0lvt-n03IyphTquI/view?usp=sharing)
