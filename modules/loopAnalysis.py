import multiprocessing
import os.path

import time

from bin import utils
import core.module
import json
import sys


def start_process():
	''' Put some debug information here if wanted
	'''
	pass


class loopAnalysis(core.module.Translator):
	__lines = {}  # lines for each thread

	__threadName = []  # NEW: name of threads, as they are found in code

	__threadIndex = {}  # index of the thread = value of threadcount when the pthread_create to that thread was discovered

	def init(self):
		pass

	def loadfromstring(self, seqcode, env):

		self.__lines = self.getInputParamValue('lines')
		self.__threadName = self.getInputParamValue('threadNames')
		self.__threadIndex = self.getInputParamValue('threadIndex')


		cs = "Number of context-switch of each thread:"
		for t in self.__lines:
			cs += "\n%s : %s" %(t, str(self.__lines[t]))
			
		if env.show_cs:
			print(cs)

		# Generating configuration file
		if env.config_file == "":
			if not env.automatic:
				print("Please set -A option if you want to automatically generate instances")
			env.config_file = env.inputfile[:-2] + \
				"_auto_config%s.json" % env.suffix

		configFile = env.config_file

		if env.automatic:
			if env.isSwarm:
				print("Generating configurations...")
		else:
			print("Loading configurations...")

		configIterator = self.generateConfigIterator(
			env, cs, configFile, env.inputfile, env.percentage)

		# Generating instances
		if env.automatic:
			if env.isSwarm:
				if env.instances_limit == 0:
					print("Generating instances with no limit")
				else:
					print("Generating instances with limit %s" %
						  env.instances_limit)

		dirname, filename = os.path.split(os.path.abspath(env.inputfile))
		swarmdirname = dirname + "/" + filename[:-2] + '.swarm%s/' % env.suffix
		instanceIterator = self.generateInstanceIterator(
			env, configIterator, seqcode)

		if env.seq_only:
			print("Sequentialization completed.")
			sys.exit(0)
		sequentializationtime = time.time() - env.starttime

		if env.isSwarm:
			pool_size = env.cores
			if pool_size == 0:
				print("0 processes created.")
				sys.exit(0)
			print("Analyzing instance(s) with " + str(env.initial_timeout) + "s timeout for " + str(
				pool_size) + " processes")
			print("======================================================")
		else:
			pool_size = 1

		if pool_size > env.instances_limit and env.instances_limit != 0:
			pool_size = env.instances_limit

		pool = multiprocessing.Pool(
			processes=pool_size, initializer=start_process)
		manager = multiprocessing.Manager()
		results = manager.Queue()
		foundbug = False
		foundtime = 0
		sentinel = object()

		def logResults(out):
			results.put(out)

		try:
			for i in range(0, pool_size):
				instance, confignumber, configintervals = next(
					instanceIterator, (sentinel, 0, 0))
				if instance is sentinel:
					break
				pool.apply_async(self.backendChain, (env, instance, confignumber, configintervals, swarmdirname,
													 filename[:-2],), callback=logResults)
			for instance, confignumber, configintervals in instanceIterator:
				out = results.get()
				if out is False and not foundbug:
					foundtime = time.time() - env.starttime
					foundbug = True
					if env.exit_on_error:
						break
				pool.apply_async(self.backendChain, (env, instance, confignumber, configintervals, swarmdirname,
													 filename[:-2],), callback=logResults)

		except KeyboardInterrupt as e:
			print("Interupted by user")
			pool.terminate()
			pool.close()
			pool.join()

		pool.close()
		pool.join()
		if not foundbug:
			while not results.empty():
				out = results.get()
				if out is False:
					foundbug = True
					foundtime = time.time() - env.starttime
					break
		backendtime = time.time() - sequentializationtime
		totaltime = time.time() - env.starttime
		if foundbug:
			self.printIsUnsafe(totaltime, foundtime,
							   env.inputfile, env.isSwarm)
		else:
			self.printIsSafe(totaltime, env.inputfile, env.isSwarm)
		return

	def substitute(self, seqCode, list, tName, startIndex):
		self.__threadIndex["main_thread"] = self.__threadIndex["main"]
		if tName == 'main':
			tName = 'main_thread'
		output = []
		i = int(seqCode[startIndex:].index(tName)) + startIndex
		output.append(seqCode[startIndex:i])
		done = False
		j = i
		ICount = 0
		count = 0
		iList = 0
		cRange = range(list[iList][0], list[iList][1] + 1)
		while (i < len(seqCode) and not done):
			if seqCode[i] == '$':
				if seqCode[i + 1] == 'I':
					if count == 0:
						s = seqCode[j:i] + '__CSEQ_rawline("IF(%s,%s,t%s_%s)");' % (
							self.__threadIndex[tName], count, tName, count + 1)
						output.append(s)
						count += 1
						i += 2
					elif ICount in cRange:
						s = seqCode[j:i] + '__CSEQ_rawline("t%s_%s: IF(%s,%s,t%s_%s)");' % (
							tName, count, self.__threadIndex[tName], count, tName, count + 1)
						output.append(s)
						count += 1
						i += 2
						if ICount == list[iList][1] and iList < len(list) - 1:
							iList += 1
							cRange = range(list[iList][0], list[iList][1] + 1)
					else:
						if seqCode[j:i] != '':
							output.append(seqCode[j:i])
							i += 2
						i += 2
					j = i
					ICount += 1
				elif seqCode[i + 1] == 'G':
					s = seqCode[j:i] + '__CSEQ_assume( __cs_pc_cs[%s] >= %s );' % (
						self.__threadIndex[tName], count)
					output.append(s)
					i += 2
					j = i
				# F
				else:
					s = seqCode[j:i] + \
						'__CSEQ_rawline("t%s_%s: ");' % (tName, count)
					output.append(s)
					i += 2
					done = True
			else:
				i += 1
		del self.__threadIndex["main_thread"]
		return i, output

	def generateConfigIterator(self, env, lines, configfile, inputfile, percentage):
		if percentage and env.isSwarm:
			configGen = utils.ConfigGeneratorPercentage(lines, env.window_percent, env.picked_window,
														env.instances_limit, consecutive=(
															not env.scatter),
														double=env.shifted_window, skiplist=env.skip_thread)

			singleConfigFilename = configfile + ".tmp"
			lenConf, result, generatedData = configGen.generatingConfigPercentage(singleConfigFilename,
																				  softLimit=env.soft_limit,
																				  hardLimit=env.hard_limit,
																				  verbose=env.debug,
																				  randomness=(
																					  not env.no_random),
																				  start=env.start_sample)

			return configGen.generatorConfigIterator(singleConfigFilename, lenConf, generatedData)

		else:
			configGen = utils.ConfigGenerator(lines, percentage, env.cluster_config, env.window_length,
											  env.window_percent,
											  env.picked_window,
											  env.instances_limit, env.config_only, consecutive=(
												  not env.scatter),
											  double=env.shifted_window, skiplist=env.skip_thread)
			singleConfigFilename = configfile + ".tmp"
			if env.isSwarm:
				if env.automatic:
					# Create a generator
					# Overwrite configuration file
					return configGen.generatingConfig(configfile, singleConfigFilename, inputfile,
													  softLimit=env.soft_limit,
													  hardLimit=env.hard_limit, randomness=(
														  not env.no_random),
													  start=env.start_sample)
				else:
					# f = open(configFilename)
					# logger.logging(f.read(), 2)
					# f.close()
					# logger.writelog()
					fd = open(configfile, "r")
					generatedData = json.load(fd)
					# print("%s" % generatedData)
					# print("%s" % len(generatedData))
					fd.close()
					# env["instances-limit"]=len(generatedData)
					return configGen.generatorConfigIterator(singleConfigFilename, len(generatedData), generatedData)
			else:
				conf = {
					's0': {}
				}
				for t in self.__lines:
					conf["s0"][t] = [[1, self.__lines[t]]]
				return configGen.generatorConfigIterator(singleConfigFilename, len(conf), conf)

	def generateInstanceIterator(self, env, configIterator, seqCode):
		if env.config_only:
			sys.exit(0)
		for config in configIterator:
			with open(config[0], "r") as config:
				jsonConfig = (json.load(config))
				configNumber, configintervals = dict(jsonConfig).popitem()
				output = []
				i = 0
				startIndex = 0
				while i < len(self.__threadName):
					tName = self.__threadName[i]
					startIndex, l = self.substitute(
						seqCode, configintervals[tName], tName, startIndex)
					listToStr = ''.join(s for s in l)
					output.append(listToStr)
					i += 1
				output.append(seqCode[startIndex:])
			instanceGenerated = ''.join(t for t in output)
			yield instanceGenerated, configNumber, configintervals

	def backendChain(self, env, instance, confignumber, configintervals, swarmdirname, filename):
		env.intervals = configintervals
		initalTimeout = env.initial_timeout
		output = instance
		analysistime = time.time()
		for env.transforms, m in enumerate(env.backendmodules):
			try:
				if env.debug:
					print("/* " + m.getname())
				m.initParams(env)
				m.setInstanceInfo(swarmdirname, filename, confignumber)
				m.loadfromstring(output, env)
				output = m.getoutput()

				# linemapping only works on Translator (C-to-C) modules
				if "inputtooutput" in dir(m):
					env.maps.append(m.outputtoinput)
					env.lastlinenoinlastmodule = m.output.count("\n")

			except Exception as e:
				print("Error while performing %s->%s:\n"
					  % (env.backendmodules[env.transforms - 1].getname() if env.transforms > 0 else "",
						 env.backendmodules[env.transforms].getname()))
				# traceback.print_exc(file=sys.stdout)
				sys.exit(1)

		cbmcresult = output[0]
		memsize = output[1]
		processedResult = self.processResult(cbmcresult, env.backend)
		analysistime = time.time() - analysistime
		if processedResult == "TRUE":
			if env.isSwarm:
				self.printNoFoundBug(confignumber.replace(
					"s", ""), memsize, analysistime)
			return True
		if processedResult == "FALSE":
			if env.isSwarm:
				self.printFoundBug(confignumber.replace(
					"s", ""), memsize, analysistime)
			return False
		sys.stdout.flush()

	def printNoFoundBug(self, index, memsize, analysistime):
		print("{0:10}{1:20}{2:10}{3:10}".format("[#" + str(index) + "]", utils.colors.GREEN + "SAFE" + utils.colors.NO,
												"%0.2fs " % analysistime, self.calcMem(memsize)))
		sys.stdout.flush()

	def printFoundBug(self, index, memsize, analysistime):
		print("{0:10}{1:20}{2:10}{3:10}".format("[#" + str(index) + "]", utils.colors.RED + "UNSAFE" + utils.colors.NO,
												"%0.2fs " % analysistime, self.calcMem(memsize)))
		sys.stdout.flush()

	def printIsSafe(self, totalTime, inputfile, isSwarm):
		if isSwarm:
			print("======================================================")
			print("Cannot find bugs in this configuration")
		print(inputfile + utils.colors.GREEN + " TRUE " +
			  utils.colors.NO + ", %0.2fs" % totalTime)
		sys.stdout.flush()

	def printIsUnsafe(self, totalTime, foundtime, inputfile, isSwarm):
		if isSwarm:
			print("======================================================")
			print("Bugs found in this configuration")
			print("Found time : " + "%0.2fs" % foundtime)
		print(inputfile + utils.colors.RED + " FALSE " +
			  utils.colors.NO + ", %0.2fs" % totalTime)
		sys.stdout.flush()

	def processResult(self, result, format):
		# Expressions to check for from the log to see whether verification went fine.
		verificationOK = {}
		# BMC backends
		verificationOK["esbmc"] = "VERIFICATION SUCCESSFUL"
		verificationOK["cbmc"] = "VERIFICATION SUCCESSFUL"
		verificationOK["blitz"] = "VERIFICATION SUCCESSFUL"
		verificationOK["llbmc"] = "No error detected."
		# AI
		verificationOK["framac"] = "__FRAMAC_spec"
		verificationOK["2ls"] = "VERIFICATION SUCCESSFUL"
		verificationOK["pagai"] = "RESULT: TRUE"  # TODO
		verificationOK["interproc"] = "TOBEPROCESSED"
		verificationOK["satabs"] = "VERIFICATION SUCCESSFUL"
		verificationOK["cpachecker"] = "Verification result: SAFE. No error path found by chosen configuration."
		# Testing
		verificationOK["klee"] = "NOSUCHTHINGFORKLEE"
		verificationOK["smack"] = "Finished with 1 verified, 0 errors"
		# Concurrent
		verificationOK["concurinterproc"] = "TOBEPROCESSED"
		verificationOK["impara"] = "VERIFICATION SUCCESSFUL"
		verificationOK["seahorn"] = "BRUNCH_STAT Result TRUE"

		# Expressions to check for from the log to check whether verification failed.
		verificationFAIL = {}
		# BMC
		verificationFAIL["cbmc"] = "VERIFICATION FAILED"
		verificationFAIL["esbmc"] = "VERIFICATION FAILED"
		verificationFAIL["blitz"] = "VERIFICATION FAILED"
		verificationFAIL["llbmc"] = "Error detected."
		# AI
		verificationFAIL["framac"] = "__FRAMAC_spec"
		verificationFAIL["2ls"] = "VERIFICATION FAILED"
		verificationFAIL["pagai"] = "RESULT: UNKNOWN"
		verificationFAIL["interproc"] = "TOBEPROCESSED"
		verificationFAIL["satabs"] = "VERIFICATION FAILED"
		verificationFAIL["cpachecker"] = "Verification result: UNSAFE."
		# testing
		verificationFAIL["smack"] = "Finished with 0 verified,"
		verificationFAIL["klee"] = "ASSERTION FAIL: "
		# Concurrent
		verificationFAIL["concurinterproc"] = "TOBEPROCESSED"
		verificationFAIL["impara"] = "VERIFICATION FAILED"
		verificationFAIL["seahorn"] = "BRUNCH_STAT Result FALSE"

		# report analysis details

		outcome = ""

		if result != "":
			backendAnswer = result if format != "klee" else "err"
			if format in ("cbmc", "esbmc",):
				for line in backendAnswer.splitlines():
					if " variables, " in line:
						splitline = line.split()
						variables = splitline[0]
						clauses = splitline[2]
					if verificationOK[format] in line:
						outcome = "TRUE"
						break
					elif verificationFAIL[format] in line:
						outcome = "FALSE"
						break
		else:
			outcome = "UNKNOWN"
		return outcome

	def calcMem(self, hmemsize):
		if (sys.platform.startswith('linux')):
			hmemsize = hmemsize / 1024.0
		elif (sys.platform.startswith('darwin')):
			hmemsize = hmemsize / (1024.0 * 1024.0)
		else:
			hmemsize = hmemsize / (1024.0)
		return "%0.2fMB" % (hmemsize)