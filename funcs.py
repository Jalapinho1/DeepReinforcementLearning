import numpy as np
import random
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import loggers as lg
from os import listdir
from os.path import isfile, join
from game import Game, GameState
from model import Residual_CNN

from agent import Agent, User

import config


def playMatchesBetweenVersions(env, run_version, player1version, player2version, EPISODES, logger, turns_until_tau0,
                               goes_first=0, swap_first=False):
    if player1version == -1:
        player1 = User('player1', env.state_size, env.action_size)
    else:
        player1_NN = Residual_CNN(config.REG_CONST, config.LEARNING_RATE, env.input_shape, env.action_size,
                                  config.HIDDEN_CNN_LAYERS)

        if player1version > 0:
            player1_network = player1_NN.read(env.name, run_version, player1version)
            player1_NN.model.set_weights(player1_network.get_weights())
        player1 = Agent('player1', env.state_size, env.action_size, config.MCTS_SIMS, config.CPUCT, player1_NN)

    if player2version == -1:
        player2 = User('player2', env.state_size, env.action_size)
    else:
        player2_NN = Residual_CNN(config.REG_CONST, config.LEARNING_RATE, env.input_shape, env.action_size,
                                  config.HIDDEN_CNN_LAYERS)

        if player2version > 0:
            player2_network = player2_NN.read(env.name, run_version, player2version)
            player2_NN.model.set_weights(player2_network.get_weights())
        player2 = Agent('player2', env.state_size, env.action_size, config.MCTS_SIMS, config.CPUCT, player2_NN)

    scores, memory, points, sp_scores = playMatches(player1, player2, EPISODES, logger, turns_until_tau0, None,
                                                    goes_first, swap_first)

    return (scores, memory, points, sp_scores)


def playMatches(player1, player2, EPISODES, logger, turns_until_tau0, memory=None, goes_first=0, swap_first=False):
    env = Game()
    scores = {player1.name: 0, "drawn": 0, player2.name: 0}
    sp_scores = {'sp': 0, "drawn": 0, 'nsp': 0}
    points = {player1.name: [], player2.name: []}

    for e in range(EPISODES):

        logger.info('====================')
        logger.info('EPISODE %d OF %d', e + 1, EPISODES)
        logger.info('====================')

        print(str(e + 1) + ' ', end='')

        state = env.reset()

        done = 0
        turn = 0
        player1.mcts = None
        player2.mcts = None

        if swap_first:
            if goes_first == 1:
                goes_first = 2
            else:
                goes_first = 1

        if goes_first == 0:
            player1Starts = random.randint(0, 1) * 2 - 1
        else:
            player1Starts = goes_first

        if player1Starts == 1:
            players = {1: {"agent": player1, "name": player1.name}
                , -1: {"agent": player2, "name": player2.name}
                       }
            logger.info(player1.name + ' plays as X')
        else:
            players = {1: {"agent": player2, "name": player2.name}
                , -1: {"agent": player1, "name": player1.name}
                       }
            logger.info(player2.name + ' plays as X')
            logger.info('--------------')

        env.gameState.render(logger)
        if type(player1) == User or type(player2) == User:
            env.gameState.printState()

        while done == 0:
            turn = turn + 1

            #### Run the MCTS algo and return an action
            if turn < turns_until_tau0:
                action, pi, MCTS_value, NN_value = players[state.playerTurn]['agent'].act(state, 1)
            else:
                action, pi, MCTS_value, NN_value = players[state.playerTurn]['agent'].act(state, 0)

            if memory != None:
                ####Commit the move to memory
                memory.commit_stmemory(env.identities, state, pi)

            logger.info('action: %d', action)
            for r in range(env.grid_shape[0]):
                logger.info(['----' if x == 0 else '{0:.2f}'.format(np.round(x, 2)) for x in
                             pi[env.grid_shape[1] * r: (env.grid_shape[1] * r + env.grid_shape[1])]])
            if MCTS_value is not None and NN_value is not None:
                logger.info('MCTS perceived value for %s: %f', state.pieces[str(state.playerTurn)],
                            np.round(MCTS_value, 2))
                logger.info('NN perceived value for %s: %f', state.pieces[str(state.playerTurn)], np.round(NN_value, 2))
            logger.info('====================')

            ### Do the action
            state, value, done, _ = env.step(
                action)  # the value of the newState from the POV of the new playerTurn i.e. -1 if the previous player played a winning move

            env.gameState.render(logger)
            if type(player1) == User or type(player2) == User:
                env.gameState.printState()

            if done == 1:
                if memory != None:
                    #### If the game is finished, assign the values correctly to the game moves
                    for move in memory.stmemory:
                        if move['playerTurn'] == state.playerTurn:
                            move['value'] = value
                        else:
                            move['value'] = -value

                    memory.commit_ltmemory()

                if value == 1:
                    logger.info('%s WINS!', players[state.playerTurn]['name'])
                    scores[players[state.playerTurn]['name']] = scores[players[state.playerTurn]['name']] + 1
                    if state.playerTurn == 1:
                        sp_scores['sp'] = sp_scores['sp'] + 1
                    else:
                        sp_scores['nsp'] = sp_scores['nsp'] + 1

                elif value == -1:
                    logger.info('%s WINS!', players[-state.playerTurn]['name'])
                    scores[players[-state.playerTurn]['name']] = scores[players[-state.playerTurn]['name']] + 1

                    if state.playerTurn == 1:
                        sp_scores['nsp'] = sp_scores['nsp'] + 1
                    else:
                        sp_scores['sp'] = sp_scores['sp'] + 1

                else:
                    logger.info('DRAW...')
                    scores['drawn'] = scores['drawn'] + 1
                    sp_scores['drawn'] = sp_scores['drawn'] + 1

                pts = state.score
                points[players[state.playerTurn]['name']].append(pts[0])
                points[players[-state.playerTurn]['name']].append(pts[1])

    return (scores, memory, points, sp_scores)


def run_tournament(env, version_run_number, num_of_episodes=2):
    path_to_models = "C://Users//edoma//PycharmProjects/AlphaZeroVersion1//run_archive//connect4//run0001//models"
    versions_nums = get_models_from_path(path_to_models)

    df = pd.DataFrame(data=np.zeros([len(versions_nums), len(versions_nums)], dtype=np.int8), index=versions_nums,
                      columns=versions_nums)
    print(df)

    for rowIndex, row in df.iterrows():  # iterate over rows
        for columnIndex, value in row.items():
            if rowIndex != columnIndex:
                version1_num = int(rowIndex)
                version2_num = int(columnIndex)
                if version1_num > version2_num:
                    continue
                scores, memory, points, sp_scores = playMatchesBetweenVersions(env, version_run_number, version1_num,
                                                                               version2_num, num_of_episodes,
                                                                               lg.logger_tourney, 0, 1, swap_first=True)
                df.loc[rowIndex, columnIndex] = scores['player1'] - scores['player2']
                df.loc[columnIndex, rowIndex] = scores['player2'] - scores['player1']

    df.to_csv('tournament_result.csv', index=False)


def evaluate_tournament():
    df = pd.read_csv('tournament_result.csv')

    df['version_number'] = df.columns
    df['points'] = df.sum(axis=1)

    sns.set()
    sns.lineplot(x='version_number', y='points', legend=False, markers=["o"], style=True, data=df)
    plt.xlabel("NN version number")
    plt.ylabel("Points")
    plt.legend(title='Max points gain: 8')
    plt.show()


def get_models_from_path(path):
    models = [f for f in listdir(path) if isfile(join(path, f))]
    versions_nums = []
    for name in models:
        first_part = name.split(".")[0]
        versions_nums.append(first_part[7:])

    return versions_nums


def evaluate_train_loss():
    # Fix for wrong export
    # df = pd.read_csv('loss2.csv',
    #                names=['train_overall_loss', 'train_value_policy', 'train_policy_loss'])
    # s = df.loc[:, 'train_overall_loss']
    # last_occurence = s.where(s == 1.56760).last_valid_index()
    # newDf = df.iloc[last_occurence::, :]
    # newDf.to_csv('loss2.csv', index=False)
    # newDf.reset_index()

    df = pd.read_csv('repaired_loss_file.csv')
    df.plot.line()
    plt.xlabel('Iteration number')
    plt.ylabel('Loss')
    plt.show()