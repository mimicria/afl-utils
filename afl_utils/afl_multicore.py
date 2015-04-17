"""
Copyright 2015 @_rc0r <hlt99@blinkenshell.org>

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import argparse
import subprocess
import sys
import time

import afl_utils

# afl_multicore global settings
afl_path = "afl-fuzz"   # in PATH


def show_info():
    print("afl_multicore %s by %s" % (afl_utils.__version__, afl_utils.__author__))
    print("Wrapper script to easily set up parallel fuzzing jobs.")
    print("")


def check_screen():
    inside_screen = False
    try:
        screen_output = subprocess.check_output("screen -ls", shell=True, stderr=subprocess.DEVNULL,
                                                universal_newlines=True)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        screen_output = e.output

    screen_output = screen_output.splitlines()

    for line in screen_output:
        if "(Attached)" in line:
            inside_screen = True

    return inside_screen


def setup_screen(slave_only, slave_num):
    windows = slave_num

    if not slave_only:
        windows += 1

    # create number of windows
    for i in range(0, windows, 1):
        subprocess.Popen(["screen"])
        time.sleep(.01)

    # go back to 1st window
    subprocess.Popen("screen -X select 1".split())


def main(argv):
    show_info()

    parser = argparse.ArgumentParser(description="afl_multicore starts several parallel fuzzing jobs, that are run \
in the background. For fuzzer stats see 'sync_dir/SESSION###/fuzzer_stats'!",
                                     usage="afl_multicore [-h] [-i] [-j SLAVE_NUMBER] [-S SESSION] [-s] [-v] input_dir\n \
sync_dir target_cmd")

    parser.add_argument("input_dir",
                        help="Input directory that holds the initial test cases (afl-fuzz's -i option).")
    parser.add_argument("sync_dir", help="afl synchronisation directory that will hold fuzzer output files \
(afl-fuzz's -o option).")
    parser.add_argument("-i", "--screen", dest="screen", action="store_const", const=True,
                        default=False, help="Interactive screen mode. Starts every afl instance in a separate screen \
window. Run from inside screen (Default: off)!")
    parser.add_argument("-j", "--slave-number", dest="slave_number", help="Number of slave instances to run (Default: \
3).", default=3)
    parser.add_argument("-S", "--session", dest="session",
                        help="Provide a name for the fuzzing session. Master outputs will be written to \
'sync_dir/SESSION000' (Default='SESSION').",
                        default="SESSION")
    parser.add_argument("-s", "--slave-only", dest="slave_only", action="store_const", const=True,
                        default=False, help="Slave-only mode, do not start a master instance (Default: off).")
    parser.add_argument("-v", "--verbose", dest="verbose", action="store_const", const=True,
                        default=False, help="For debugging purposes do not redirect stderr/stdout of the created \
subprocesses to /dev/null (Default: off). Check 'nohup.out' for further outputs.")
    parser.add_argument("target_cmd", nargs="+", help="Path to the target binary and its command line arguments. \
Use '@@' to specify crash sample input file position (see afl-fuzz usage).")

    args = parser.parse_args(argv[1:])

    if args.input_dir:
        input_dir = args.input_dir
    else:
        print("No valid directory provided for <INPUT_DIR>!")
        return

    if args.sync_dir:
        sync_dir = args.sync_dir
    else:
        print("No valid directory provided for <sync_dir>!")
        return

    if args.screen:
        if not check_screen():
            print("When using screen mode, please run afl_multicore from inside a screen session!")
            return

        setup_screen(args.slave_only, args.slave_number)

    if not args.slave_only:
        # compile command-line for master
        # $ afl-fuzz -i <input_dir> -o <sync_dir> -M <session_name>.000 </path/to/target.bin> <target_args>
        master_cmd = "%s -i %s -o %s -M %s000 -- %s" % (afl_path, input_dir, sync_dir, args.session, " ".join(args.target_cmd))
        print("Starting master instance...")

        if not args.screen:
            if not args.verbose:
                master = subprocess.Popen(" ".join(['nohup', master_cmd]).split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                master = subprocess.Popen(" ".join(['nohup', master_cmd]).split())
            print("Master 000 started (PID: %d)" % master.pid)
        else:
            screen_cmd = ["screen", "-X", "eval", "exec %s" % master_cmd, "next"]
            subprocess.Popen(screen_cmd)
            print("Master 000 started inside new screen window")

    # compile command-line for slaves
    # $ afl-fuzz -i <input_dir> -o <sync_dir> -S <session_name>.NNN </path/to/target.bin> <target_args>
    print("Starting slave instances...")
    for i in range(1, int(args.slave_number)+1, 1):
        slave_cmd = "%s -i %s -o %s -S %s%03d -- %s" % (afl_path, input_dir, sync_dir, args.session, i, " ".join(args.target_cmd))

        if not args.screen:
            if not args.verbose:
                slave = subprocess.Popen(" ".join(['nohup', slave_cmd]).split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                slave = subprocess.Popen(" ".join(['nohup', slave_cmd]).split())
            print("Slave %03d started (PID: %d)" % (i, slave.pid))
        else:
            screen_cmd = ["screen", "-X", "eval", "exec %s" % slave_cmd, "next"]
            subprocess.Popen(screen_cmd)
            print("Slave %03d started inside new screen window" % i)

    print("")
    if not args.screen:
        print("For progress info check: %s/%sxxx/fuzzer_stats!" % (args.sync_dir, args.session))
    else:
        print("Check the newly created screen windows!")


if __name__ == "__main__":
    main(sys.argv)