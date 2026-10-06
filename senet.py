#!/usr/bin/env python3
"""Senet —— 古埃及塞尼特棋(规则重构版).

3x10 棋盘,每方 5 子,掷四根半圆签(点数 1-5)走子。
特殊格:26 美丽之屋(必须精确落子,不可跳过)、27 水之屋(落到退回 15)、
28 三真理之屋(需掷 3 离开)、29 拉之屋(需掷 2 离开)、30 终点(需掷 1 出局)。
落到对方孤子格则交换位置;相邻有对方子保护则不可落。
先把 5 子全部送出局者胜。

纯标准库,Python 3.10+。
"""

import argparse
import random
import sys

N_SQUARES = 30
N_PIECES = 5

STICK_VALUES = (1, 2, 3, 4, 5)
# 四根半圆签:亮面朝上 1/2/3/4 根对应点数 1-4,全暗面朝上对应 5
STICK_WEIGHTS = (1, 4, 6, 4, 1)

BEAUTY = 26    # 美丽之屋:必须精确落子,不能跳过
WATER = 27     # 水之屋:落到则退回 15
TRUTHS = 28    # 三真理之屋:需掷出 3 才能离开
RE_ATOUM = 29  # 拉之屋:需掷出 2 才能离开
LAST = 30      # 终点:需掷出 1 才能出局

SPECIAL_NAMES = {
    BEAUTY: "美丽之屋",
    WATER: "水之屋",
    TRUTHS: "三真理之屋",
    RE_ATOUM: "拉之屋",
    LAST: "终点",
}

GLYPH = {None: "·", 0: "●", 1: "○"}
NAMES = ("甲", "乙")


class IllegalMove(Exception):
    """非法走法。"""


class Senet:
    """塞尼特棋局。board[1..30] 为 None/0/1;走法记为 (起点, 终点),终点 None 表出局。"""

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.board = [None] * (N_SQUARES + 1)
        for sq in (1, 3, 5, 7, 9):
            self.board[sq] = 0
        for sq in (2, 4, 6, 8, 10):
            self.board[sq] = 1
        self.off = [0, 0]
        self.turn = 0
        self.half_moves = 0

    # ---- 基础 ----

    def throw_sticks(self):
        return self.rng.choices(STICK_VALUES, weights=STICK_WEIGHTS, k=1)[0]

    def pieces(self, player):
        return [sq for sq in range(1, N_SQUARES + 1) if self.board[sq] == player]

    def _protected(self, sq, player):
        """sq 上的 player 棋子是否有相邻同伴保护。"""
        for nb in (sq - 1, sq + 1):
            if 1 <= nb <= N_SQUARES and self.board[nb] == player:
                return True
        return False

    # ---- 走法 ----

    def legal_moves(self, player, throw):
        moves = []
        for s in self.pieces(player):
            if s == LAST:
                if throw == 1:
                    moves.append((s, None))
                continue
            if s == TRUTHS and throw != 3:
                continue
            if s == RE_ATOUM and throw != 2:
                continue
            t = s + throw
            if t > LAST:
                # 28 掷 3 / 29 掷 2 直接出局
                if (s == TRUTHS and throw == 3) or (s == RE_ATOUM and throw == 2):
                    moves.append((s, None))
                continue
            if s < BEAUTY < t:
                continue  # 不可跳过美丽之屋
            occ = self.board[t]
            if occ == player:
                continue
            if occ is not None and self._protected(t, occ):
                continue  # 被保护的对方子不可吃
            moves.append((s, t))
        return moves

    def apply_move(self, player, move, throw):
        if move not in self.legal_moves(player, throw):
            raise IllegalMove(f"非法走法: {move}(掷出 {throw})")
        s, t = move
        self.board[s] = None
        if t is None:
            self.off[player] += 1
        else:
            occ = self.board[t]
            if occ is not None and occ != player:
                self.board[s] = occ  # 交换位置
            self.board[t] = player
            if t == WATER:
                self.board[t] = None
                dest = 15
                while dest >= 1 and self.board[dest] is not None:
                    dest -= 1
                if dest >= 1:
                    self.board[dest] = player
                else:  # 理论上不可能,兜底
                    self.board[t] = player
        self.half_moves += 1
        self.turn = 1 - self.turn

    # ---- 终局 ----

    def winner(self):
        for p in (0, 1):
            if self.off[p] >= N_PIECES:
                return p
        return None

    def is_over(self):
        return self.winner() is not None


# ---- AI ----

def ai_choose(game, player, throw, rng):
    """贪心:出局 > 交换 > 推进 > 特殊格微调。"""
    moves = game.legal_moves(player, throw)
    if not moves:
        return None
    best, best_score = None, -1e18
    for s, t in moves:
        score = rng.random()  # 平局随机打破
        if t is None:
            score += 100.0
        else:
            occ = game.board[t]
            if occ is not None and occ != player:
                score += 30.0
            score += t * 0.5
            if t == BEAUTY:
                score += 5.0
            if t == WATER:
                score -= 5.0
        if score > best_score:
            best, best_score = (s, t), score
    return best


# ---- 对局 ----

def play_game(seed=None, max_half_moves=2000, verbose=False):
    game = Senet(seed=seed)
    while not game.is_over() and game.half_moves < max_half_moves:
        player = game.turn
        throw = game.throw_sticks()
        move = ai_choose(game, player, throw, game.rng)
        if move is None:
            game.turn = 1 - game.turn  # 无棋可走,轮空
            game.half_moves += 1
            continue
        game.apply_move(player, move, throw)
        if verbose:
            s, t = move
            dest = "出局" if t is None else str(t)
            print(f"{NAMES[player]} 掷 {throw}: {s} -> {dest}")
    return game


def play_auto(games, seed):
    rng = random.Random(seed)
    wins = [0, 0]
    draws = 0
    total_moves = 0
    for i in range(games):
        g = play_game(seed=rng.randrange(1 << 30))
        w = g.winner()
        if w is None:
            draws += 1
        else:
            wins[w] += 1
        total_moves += g.half_moves
    return wins, draws, total_moves


# ---- 界面 ----

def render(game):
    rows = [list(range(1, 11)), list(range(20, 10, -1)), list(range(21, 31))]
    lines = []
    for r in rows:
        cells = []
        for sq in r:
            mark = "*" if sq in SPECIAL_NAMES else " "
            cells.append(f"{sq:2d}{GLYPH[game.board[sq]]}{mark}")
        lines.append(" ".join(cells))
    lines.append(f"出局: {NAMES[0]} {game.off[0]} / {NAMES[1]} {game.off[1]}"
                 f"  (* 特殊格:26 美丽之屋/27 水之屋/28 三真理/29 拉之屋/30 终点)")
    return "\n".join(lines)


def play_interactive(seed=None):
    if not sys.stdin.isatty():
        print("交互模式需要终端;无头演示请用 --auto", file=sys.stderr)
        sys.exit(2)
    game = Senet(seed=seed)
    human = 0
    print("塞尼特棋:你是 ●(甲),AI 是 ○(乙)。输入走法序号。")
    while not game.is_over():
        print()
        print(render(game))
        player = game.turn
        throw = game.throw_sticks()
        print(f"{NAMES[player]} 掷出 {throw}")
        if player == human:
            moves = game.legal_moves(player, throw)
            if not moves:
                print("无棋可走,轮空。")
                game.turn = 1 - game.turn
                continue
            for i, (s, t) in enumerate(moves):
                print(f"  {i}: {s} -> {'出局' if t is None else t}")
            try:
                idx = int(input("选走法: ").strip())
                move = moves[idx]
            except (ValueError, IndexError):
                print("输入无效,轮空。")
                game.turn = 1 - game.turn
                continue
            game.apply_move(player, move, throw)
        else:
            move = ai_choose(game, player, throw, game.rng)
            if move is None:
                print("AI 无棋可走,轮空。")
                game.turn = 1 - game.turn
                continue
            s, t = move
            print(f"AI: {s} -> {'出局' if t is None else t}")
            game.apply_move(player, move, throw)
    print()
    print(render(game))
    print(f"{NAMES[game.winner()]} 胜!")


def main(argv=None):
    ap = argparse.ArgumentParser(description="塞尼特棋(古埃及棋,规则重构版)")
    ap.add_argument("--auto", action="store_true", help="AI 对 AI 自动演示")
    ap.add_argument("--games", type=int, default=10, help="自动演示局数")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--verbose", action="store_true", help="自动演示打印每步")
    args = ap.parse_args(argv)
    if args.auto:
        if args.verbose:
            g = play_game(seed=args.seed, verbose=True)
            w = g.winner()
            print(f"胜者: {NAMES[w] if w is not None else '和棋'}({g.half_moves} 半回合)")
        else:
            wins, draws, total = play_auto(args.games, args.seed)
            print(f"共 {args.games} 局: {NAMES[0]}胜 {wins[0]},"
                  f"{NAMES[1]}胜 {wins[1]},和棋 {draws},"
                  f"平均 {total / args.games:.1f} 半回合/局")
    else:
        play_interactive(seed=args.seed)


if __name__ == "__main__":
    main()
