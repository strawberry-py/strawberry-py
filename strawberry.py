from __future__ import annotations

import asyncio
import os
import platform
import sys
import traceback
from pathlib import Path
from typing import Dict

import dotenv
import pyinstrument

import discord

from pie import exceptions
from pie.bot import Strawberry
from pie.cli import COLOR

# Setup checks

dotenv.load_dotenv(".env")  # Reload dotenv

profiler: pyinstrument.Profiler = None
if os.getenv("PROFILER_ENABLED", "False") == "True":
    try:
        interval = float(os.getenv("PROFILER_INTERVAL", 0.001))
        profiler = pyinstrument.Profiler(interval=interval)
        profiler.start()
        print("Profiler started!")
    except ValueError:
        print("Profiler could not start - invalid value for PROFILER_INTERVAL")


def test_dotenv() -> None:
    if type(os.getenv("DB_STRING")) != str:
        raise exceptions.DotEnvException("DB_STRING is not set.")
    if type(os.getenv("TOKEN")) != str:
        raise exceptions.DotEnvException("TOKEN is not set.")


test_dotenv()


def print_versions():
    python_version: str = "{0.major}.{0.minor}.{0.micro}".format(sys.version_info)
    python_release: str = f"{platform.machine()} {platform.version()}"
    dpy_version: str = "{0.major}.{0.minor}.{0.micro}".format(discord.version_info)

    print("Starting with:")
    print(f"- Python version {COLOR.green}{python_version}{COLOR.none}")
    print(f"- Python release {python_release}")
    print(f"- discord.py {COLOR.green}{dpy_version}{COLOR.none}")

    print("Using repositories:")

    init = Path(__file__).resolve()
    module_dirs: Path = sorted((init.parent / "modules").glob("*"))

    dot_git_paths: Dict[str, Path] = {}
    dot_git_paths["base"] = init.parent / ".git"

    for module_dir in module_dirs:
        if (module_dir / ".git").is_dir():
            dot_git_paths[module_dir.name] = module_dir / ".git"

    longest_repo_name: int = max([len(name) for name in dot_git_paths.keys()])

    def print_repository_version(
        repository_name: str,
        repository_version: str,
        *,
        color: str = COLOR.green,
    ):
        print(
            "- "
            f"{repository_name.ljust(longest_repo_name)} "
            f"{color}{repository_version}{COLOR.none}"
        )

    for repo_name, dot_git_dir in dot_git_paths.items():
        head: Path = dot_git_dir / "HEAD"
        if not head.is_file():
            print_repository_version(
                repo_name,
                "none, .git/HEAD is missing",
                color=COLOR.yellow,
            )
            continue

        with head.open("r") as handle:
            ref_path: str = handle.readline().strip().split(" ")[1]

        ref: Path = dot_git_dir / ref_path
        if not ref.is_file():
            print_repository_version(
                repo_name,
                "none, .git/HEAD points to invalid location",
                color=COLOR.yellow,
            )
            continue

        with ref.open("r") as handle:
            commit: str = handle.readline().strip()

        print_repository_version(repo_name, commit)


print_versions()


# Move to the script's home directory


root_path = os.path.dirname(os.path.abspath(__file__))
os.chdir(root_path)
del root_path


async def main():
    async with Strawberry():
        await Strawberry().start()
    return Strawberry().exit_code


try:
    result = asyncio.run(main())
except asyncio.exceptions.CancelledError:
    print("Strawberry-py process was interrupted.")
except Exception as e:
    print(traceback.format_exc(e))
    result = 2

if profiler:
    dotenv.set_key(
        dotenv_path=".env",
        key_to_set="PROFILER_ENABLED",
        value_to_set="False",
        quote_mode="never",
        export=False,
    )
    profiler.stop()
    profiler.write_html("profiler_results.html")

print(f"Exit code: {result}")
if result:
    print("The strawberry-py should restart.")
exit(result)
