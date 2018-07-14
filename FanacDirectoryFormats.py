import collections

# ============================================================================================
global g_FanacFanzineDirectoryFormats
g_FanacFanzineDirectoryFormats={}

FanacDirectoryFormat=collections.namedtuple("FanacDirectoryFormat", "Num1, Num2, DirName")

class FanacDirectoryFormats:

    def __init__(self):
        global g_FanacFanzineDirectoryFormats
        if len(g_FanacFanzineDirectoryFormats) == 0:
            self.ReadFanacOrgFormatsTxt()
        return

    def List(self):
        return g_FanacFanzineDirectoryFormats

    def GetFormat(self, dirname):
        if dirname in g_FanacFanzineDirectoryFormats.keys():
            return g_FanacFanzineDirectoryFormats[dirname]
        return (1, 1, dirname)  # The default format

    def ReadFanacOrgFormatsTxt(self):
        global g_FanacFanzineDirectoryFormats
        if len(g_FanacFanzineDirectoryFormats) > 0:
            return g_FanacFanzineDirectoryFormats

        print("----Begin reading Fanac fanzine directory formats.txt")


        # Next we read the table of fanac.org file formats.
        # Fanac.org's fanzines are *mostly* in one format, but there are at least a dozen different ways of presenting them.
        # The table will allow us to pick the right method for reading the index.html file and locating the right issue URL
        try:
            f=open("Fanac fanzine directory formats.txt", "r")
        except:
            print("Can't open 'Fanac fanzine directory formats.txt'")
            exit(0)
        # Read the file.  Lines beginning with a # are comments and are ignored
        # Date lines consist of a commz-separated list:
        #       The first two elements are code numbers
        #       The remaining elements are directories in fanac.org/fanzines
        #       We create a dictionary of fanzine directory names in lower case.
        #       The value of each directory entry is a tuple consisting of Name (full case) folowed by the two numbers.
        for line in f:
            line=line.strip()  # Make sure there are no leading or traling blanks
            if len(line)==0 or line[0]=="#":  # Ignore some lines
                continue
            # We apparently have a data line. Split it into tokens. Remove leading and trailing blanks, but not internal blanks.
            spl=line.split(",")
            if len(spl)<3:  # There has to be at least three tokens (the two numbers and at least one directory name)
                print("***Something's wrong with "+line)
                continue
            nums=spl[:2]
            spl=spl[2:]
            for dir in spl:
                g_FanacFanzineDirectoryFormats[dir.lower().strip()]=FanacDirectoryFormat(int(nums[0]), int(nums[1]), dir)
        print("----Done reading Fanac fanzine directory formats.txt")

        return g_FanacFanzineDirectoryFormats