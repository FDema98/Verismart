#!/usr/bin/env python
import os.path
import subprocess
import shlex
import os
import os.path
import sys
import getopt

def usage(cmd, errormsg="", showHelp=True):
	if showHelp:
		print("")
		print("  Lazy CSeq")
		print("")
		print("Usage: ")
		print("   %s [options] -i FILE (.c)" % cmd)
		print("")
	if errormsg:
		print(errormsg + "\n")

def main(args):
	cmd = args[0]
	cmdline = os.path.dirname(sys.argv[0]) + "/"
	from bin import config
	cmdline += config.relpath["translator"]
	for argument in args[1:]:
		if "-h" in argument:
			usage(cmd)
			print("======================================================================================")
			subprocess.run(shlex.split(cmdline + " -h"))
			sys.exit(1)
		if "-H" in argument:	
			usage(cmd)
			print("======================================================================================")
			subprocess.run(shlex.split(cmdline + " -H"))
			sys.exit(1)
		cmdline += " %s" % argument
	subprocess.run(shlex.split(cmdline))
	sys.exit(0)


if __name__ == "__main__":
	main(sys.argv[0:])