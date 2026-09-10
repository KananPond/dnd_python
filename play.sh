#!/bin/sh
# dnd —— 通用启动脚本 / universal launcher
#
# 支持：Linux、macOS、Windows 上的 WSL2（Ubuntu/Debian/… 发行版内）。
# Windows 原生 cmd / PowerShell / Git Bash / Cygwin 不支持 curses，不在支持范围内 —— 请用 WSL2。
#
#   用法 / usage:
#     ./play.sh                      启动游戏（进入建角界面）
#     ./play.sh --seed 42 --name Aria --class wizard --race elf
#     ./play.sh --check              只做环境自检，不启动游戏
#     ./play.sh --help               转发给游戏显示全部参数
#
#   环境变量:
#     DND_PYTHON=/path/to/python3    指定解释器（默认自动探测 python3 / python）
#
# 这个脚本只做三件事：确认环境能跑 → 必要时把终端调成 UTF-8 → 交给 python3 -m dnd。
# 除了解释器探测与 curses/版本校验，它不做任何"魔法"，所有参数原样转发。

set -u

# ---------------------------------------------------------------- 定位仓库根目录
script=$0
case $script in
  */*) ;;
  *) script=$(command -v -- "$script" 2>/dev/null || printf '%s' "$script") ;;
esac
case $script in
  /*) ;;
  *) script=$PWD/$script ;;
esac

# 取脚本所在目录。这里**刻意不做符号链接解析**：`readlink -f` 是 GNU 扩展，
# macOS 自带 readlink 没有 -f，用它会让脚本在 mac 上直接失败（而 mac 正是必须支持的平台之一）。
# 所以仓库怎么放就怎么调：`cd <仓库> && ./play.sh`，或 `sh <仓库绝对路径>/play.sh`。
# 软链到 ~/.local/bin 的用法不支持（会误判仓库根目录）。
root=''
sdir=$(CDPATH= cd -- "$(dirname -- "$script")" 2>/dev/null && pwd -P) || sdir=''
if [ -n "$sdir" ]; then
  root=$sdir
else
  # 逐级取 dirname，避免依赖外部 dirname（PATH 被清空时也能跑）
  root=$script
  while :; do
    base=${root##*/}
    case $base in
      ''|'.'|'..')
        root=${root%/*}
        [ -n "$root" ] || root=/
        ;;
      *) break ;;
    esac
  done
  root=${root%/*}
  [ -n "$root" ] || root=/
  case $root in
    /*) ;;
    *) root=$PWD/$root ;;
  esac
fi
cd -- "$root" || { printf 'dnd: 无法进入仓库目录 %s\n' "$root" >&2; exit 1; }

# ---------------------------------------------------------------- 输出小工具
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ] && [ "${TERM:-}" != "dumb" ]; then
  A=$(printf '\033[33m'); D=$(printf '\033[2m'); R=$(printf '\033[0m')
else
  A=''; D=''; R=''
fi
say()  { printf '%s\n' "$*"; }
note() { printf '%s%s%s\n' "$D" "$*" "$R"; }
err()  { printf '%s\ndnd: %s\n' "$A" "$*" >&2; }
hint_inline() { printf '%s  ↳ %s%s\n' "$D" "$*" "$R" >&2; }

# ---------------------------------------------------------------- 1. 平台判定
uname_s=$(uname -s 2>/dev/null || echo unknown)
is_wsl=no
if [ -r /proc/version ] && grep -qi 'microsoft\|wsl' /proc/version 2>/dev/null; then
  is_wsl=yes
fi

case $uname_s in
  MINGW*|MSYS*|CYGWIN*|Windows*)
    err "检测到 Windows 原生环境（$uname_s）：这里的 Python 没有 curses，跑不了本游戏的 TUI。"
    note "Detected native Windows ($uname_s); its Python has no curses support."
    say ""
    say "请在 WSL2 里运行 / please run inside WSL2:"
    say "  1) Windows 终端里执行:  wsl --install -d Ubuntu"
    say "  2) 进入 WSL:            wsl"
    say "  3) 进入 WSL 里 cd 到本仓库（Windows 盘上的仓库在 WSL 下是 /mnt/<盘符>/…），再执行 ./play.sh"
    say ""
    note "本仓库刻意不做 Windows 原生适配：Windows 原生 Python 没有标准库 curses，"
    note "强行支持需要额外依赖（windows-curses），与「零第三方依赖」的设计目标冲突。"
    exit 2
    ;;
esac

# ---------------------------------------------------------------- 2. 解释器探测
have() { command -v -- "$1" >/dev/null 2>&1; }

pick_python() {
  if [ -n "${DND_PYTHON:-}" ]; then
    if ! have "$DND_PYTHON"; then
      err "DND_PYTHON=$DND_PYTHON 找不到这个可执行文件。"
      hint_inline "改成本机 python3 的绝对路径，或 unset DND_PYTHON 让脚本自动探测。"
      return 2
    fi
    printf 'DND_PYTHON=%s\n' "$DND_PYTHON" >&2
    printf '%s\n' "$DND_PYTHON"
    return 0
  fi

  # 依次试 python3 / python，用「能不能真的跑起来 + 版本 ≥ 3.10 + 有 curses」作为唯一标准。
  # 这样能自动排除 Windows Store 的 python3 占位程序（它只会打开应用商店）。
  for cand in python3 python; do
    have "$cand" || continue
    if out=$("$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 3)' 2>&1); then
      printf '%s\n' "$cand"
      return 0
    fi
    case $? in
      3) note "跳过 $cand（版本 $("$cand" -V 2>&1 | head -n 1)：需要 ≥ 3.10）" ;;
      *) note "跳过 $cand（$cand -c 执行失败，可能是应用商店占位程序）" ;;
    esac
  done
  return 1
}

PY=$(pick_python) || pyfail=yes
if [ "${pyfail:-no}" = yes ]; then
  err "没有找到可用的 Python ≥ 3.10。"
  note "No usable Python >= 3.10 found."
  say ""
  say "安装方法 / how to install:"
  say "  Debian/Ubuntu/WSL:  sudo apt update && sudo apt install -y python3"
  say "  Fedora/RHEL:        sudo dnf install -y python3"
  say "  Arch:               sudo pacman -S python"
  say "  macOS (Homebrew):   brew install python"
  say "  macOS (系统自带):   没有 python3 时执行 xcode-select --install，"
  say "                      或用 /usr/bin/python3（≥3.9，但本游戏需要 ≥3.10）"
  say ""
  note "已装好但仍报错？可能只是名字不同，直接指定："
  note "  DND_PYTHON=\$(command -v python3.12) ./play.sh"
  exit 2
fi

# ---------------------------------------------------------------- 3. 先问清终端事实
# 只起一个 python 子进程把要用的信息一次拿全，避免 --version / -c 来回拉起来。
# 中文界面 + Unicode 框线都依赖 UTF-8：macOS 的 Terminal.app 在未设置 locale 时，
# Python 的 stdout 会退回 ascii，导致中文/框线乱码 —— 后面据此决定是否补一个 UTF-8 locale。
#
# 两个必须遵守的写法（都踩过坑）：
#   1) 用 `python -c '代码'`，**绝不用 here-document**：`sh` 的 here-doc 是从脚本自己的
#      stdin 读的，会把终端键盘输入一并吞掉（脚本是交互式启动器，这会让游戏收不到按键）。
#   2) 终端尺寸取 /dev/tty，不信 fd 1：命令替换会把 fd 1 接到管道上，fd 1 上必然 ENOTTY，
#      只能拿到假的 80x24；/dev/tty 不受重定向影响（stty size / tput cols 同理）。
probe=$("$PY" -c '
import os, sys


def term_size():
    if os.isatty(0) or os.isatty(1) or os.isatty(2):
        for fd in (1, 0):
            try:
                return os.get_terminal_size(fd)
            except OSError:
                pass
    try:
        fd = os.open("/dev/tty", os.O_RDONLY)
    except OSError:
        return os.terminal_size((80, 24))
    try:
        return os.get_terminal_size(fd)
    except OSError:
        return os.terminal_size((80, 24))
    finally:
        os.close(fd)


size = term_size()
print(sys.version.split()[0])
print((sys.stdout.encoding or "?").lower().replace("-", ""))
print("%dx%d" % (size.columns, size.lines))
print(os.environ.get("TERM") or "")
' 2>/dev/null) || probe=""
probe=$(printf '%s\n' "$probe" | sed '/^$/d; s/^[[:space:]]*//; s/[[:space:]]*$//')
py_ver=$(printf '%s\n' "$probe" | sed -n 1p);  py_ver=${py_ver:-?}
enc=$(printf '%s\n' "$probe" | sed -n 2p);     enc=${enc:-?}
dims=$(printf '%s\n' "$probe" | sed -n 3p);    dims=${dims:-?x?}
term=${TERM:-$(printf '%s\n' "$probe" | sed -n 4p)}
cols=${dims%%x*}; rows=${dims##*x}
# TTY 判定交给 shell 自己做：test -t 1 直接问 fd 1，不受子进程启动时机影响。
if [ -t 1 ]; then ttyok=yes; else ttyok=no; fi

# ---------------------------------------------------------------- 4. 依赖自检（版本 / curses）
# 结果落在 dep_ok / dep_why，供 --check 报告与启动前拦截共用一份结论（避免"报告说好的、
# 启动却失败"这种自检报告与真实结果不一致的坑）。
dep_ok=yes
dep_why=''
dep_err=$("$PY" -c '
import sys

problems = []
if sys.version_info < (3, 10):
    problems.append(
        "Python %d.%d 太旧（本游戏要求 >= 3.10）。/ Python %d.%d is too old (>= 3.10 required)."
        % (*sys.version_info[:2], *sys.version_info[:2])
    )

try:
    import curses  # noqa: F401
except ImportError:
    problems.append(
        "当前 Python 没有 curses 模块 —— Windows 原生 Python 就是这样，请改用 WSL2 终端。\n"
        "This Python has no curses module (typical on native Windows): please use a WSL2 terminal."
    )
except Exception as exc:  # 装了但 import 就炸（少见）
    problems.append("curses 模块导入失败 / failed to import curses: %r" % (exc,))

if problems:
    print("\n".join("dnd: " + p for p in problems), file=sys.stderr)
    sys.exit(2)
' 2>&1) || dep_ok=no
[ "$dep_ok" = yes ] || dep_why=$(printf '%s' "$dep_err" | sed -n '1p' | sed 's/^dnd: //')
[ -n "$dep_why" ] || dep_why="解释器自检未通过且没有输出原因（可能是解释器被替换成了外壳脚本/占位程序）"

# 环境自检报告（--check）。刻意"只报告、不拦截"：正是跑不起来的时候才最需要它，
# 所以它必须在依赖缺失、甚至不是真实终端时也能把结论打出来。
run_check() {
  if [ "$dep_ok" = no ]; then
    say "${A}dnd 环境自检未通过：解释器不满足要求 / interpreter check failed${R}"
  elif [ "$ttyok" = no ]; then
    say "${A}dnd 环境自检通过（但当前环境跑不了 TUI）/ environment OK, but cannot run the TUI here${R}"
  else
    say "${A}dnd 环境自检通过 / environment check passed${R}"
  fi
  say "  仓库      $(pwd)"
  say "  平台      $uname_s$([ "$is_wsl" = yes ] && printf ' (WSL2)')"
  say "  解释器    $PY — Python $py_ver"
  if [ "$dep_ok" = yes ]; then
    say "  依赖      curses 可用；游戏本体零第三方依赖"
  else
    say "  依赖      ✗ $dep_why"
  fi
  say "  终端      stdout TTY: $ttyok   TERM=${term:-<空>}   encoding=$enc"
  say "  locale    LC_ALL=${LC_ALL:-<未设>}  LC_CTYPE=${LC_CTYPE:-<未设>}  LANG=${LANG:-<未设>}"
  say "  尺寸      ${dims}（最小 62x18，建议 >= 100x30）"
  say "  存档目录  $(pwd)/saves"
  say ""
  if [ "$dep_ok" = no ]; then
    note "先解决上面这条依赖问题（多数情况是"换一个带 curses 的 Python"，Windows 用户请用 WSL2）。"
  elif [ "$ttyok" = yes ]; then
    [ "$enc" = utf8 ] || note "注意：编码不是 UTF-8，中文/框线可能乱码；可加 --ascii，或把终端设为 UTF-8。"
    note "接下来直接跑 ./play.sh 即可开始游戏。"
  else
    note "这里不是真实终端，所以只能自检。/ Not a real terminal: self-check only."
    note "请在终端窗口里跑 ./play.sh；无界面验证用 ./play.sh --headless-demo 300 --seed 5"
  fi
}

# ---------------------------------------------------------------- 5. 子命令分流
# 这三类用法本来就不需要终端（无头自检 / 列存档 / 打印名册）：直接交给 python，
# 不干预 locale 与终端尺寸，这样它们也能在 CI、cron、ssh 非交互会话里用。
if [ $# -gt 0 ]; then
  for arg in "$@"; do
    case $arg in
      --headless-demo|--list-saves|--roster)
        exec "$PY" -m dnd "$@" ;;
      --check)
        # 自检放在最前面：跑不起来的时候才最需要它，所以它必须在
        # 「不是真实终端」时也能给出完整报告，而不是跟着一起报错退出。
        run_check; exit 0 ;;
    esac
  done
fi

# ---------------------------------------------------------------- 6. 启动前拦截
# 依赖自检的结论（dep_ok）已经在第 4 节算过了，这里只负责"不通过就别启动"。
if [ "$dep_ok" = no ]; then
  printf '%s\n' "$dep_err" >&2   # 把 python 的完整原因原样打出来
  hint_inline "只是想在无终端环境里验证代码？./play.sh --headless-demo 300 --seed 5"
  exit 2
fi
if [ "$ttyok" = no ]; then
  err "stdout 不是交互式终端 —— 本游戏的 TUI 需要真实终端。"
  note "请在终端窗口里运行 ./play.sh（不要用管道/重定向/IDE 输出面板）。"
  hint_inline "无界面自检：./play.sh --headless-demo 300 --seed 5"
  exit 2
fi

# ---------------------------------------------------------------- 7. 终端环境：UTF-8 与尺寸
if [ "$enc" != utf8 ]; then
  cur=${LC_ALL:-${LC_CTYPE:-${LANG:-}}}
  avail=$(locale -a 2>/dev/null || true)
  for want in "${cur:-}" C.UTF-8 en_US.UTF-8 UTF-8; do
    [ -n "$want" ] || continue
    if printf '%s\n' "$avail" | grep -qix -- "$want"; then
      LC_CTYPE=$want; export LC_CTYPE
      enc=$(LC_CTYPE=$want "$PY" -c 'import sys; print((sys.stdout.encoding or "?").lower().replace("-",""))' 2>/dev/null || printf '%s' "$enc")
      note "终端编码不是 UTF-8，已临时切到 LC_CTYPE=$want 以保证中文/框线正常。"
      break
    fi
  done
  if [ "$enc" != utf8 ]; then
    note "提示：终端编码似乎不是 UTF-8（$enc），界面可能乱码。"
    note "可加 --ascii 用纯 ASCII 框线，或把终端/SSH 设为 UTF-8（例如 export LANG=en_US.UTF-8）。"
  fi
fi

if [ -z "${TERM:-}" ]; then
  TERM=xterm-256color; export TERM
  term=$TERM
fi

case $cols in ''|*[!0-9]*) cols=80 ;; esac
case $rows in ''|*[!0-9]*) rows=24 ;; esac
if [ "$cols" -lt 62 ] || [ "$rows" -lt 18 ]; then
  note "提示：当前终端 ${cols}x${rows} 小于最小可运行尺寸 62x18，请把窗口调大。"
elif [ "$cols" -lt 100 ] || [ "$rows" -lt 30 ]; then
  note "提示：当前终端 ${cols}x${rows}；宽度 >= 100 才会显示右侧「冒险者档案」栏（建议 >= 100x30）。"
fi
if [ "$term" = dumb ]; then
  note "提示：TERM=dumb，curses 界面无法正常绘制；请换一个真实终端。"
fi

# ---------------------------------------------------------------- 8. 启动
note "dnd · Python $py_ver · $(pwd)"
exec "$PY" -m dnd "$@"
