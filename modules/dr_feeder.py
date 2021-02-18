import feeder, core.module, core.parser, core.utils

class dr_feeder(feeder.feeder, object):

    def loadfromstring(self, string, env):
        if env.justseq:
            seqfile = core.utils.rreplace(env.inputfile, '/', '/'+env.prefix, 1) if '/' in env.inputfile else env.prefix + env.inputfile
            if env.outputfile is not None and env.outputfile != '':
                seqfile = env.outputfile
            newstring = string
            core.utils.saveFile(seqfile, string)
        else:
            super(self.__class__, self).loadfromstring(string, env)
        return


