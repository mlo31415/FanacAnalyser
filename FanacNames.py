import collections
import Helpers
import re

# This is a tuple which associates all the different forms of a fanzine's name on fanac.org.
# It does *not* try to deal with namechanges!
#   JoeName is the name used by Joe in his database (e.g., 1942fanzines.pdf on fanac.org)
#   DisplayName is the name we prefer to use for people-readable materials
#   FanacStandardName is the human-readable name used in the big indexes under modern and classic fanzines
#   RetroNsame is the named used in the Retro_Hugos.html file on fanac.org
FanacNameXYZ=collections.namedtuple("FanacName", "JoesName, DisplayName, FanacStandardName, RetroName")

global g_fanacNameTuples  # Holds all the accumulated name tuples
g_fanacNameTuples=[]

# We will build up a list of these tuples with one or more access functions so that the appropriate tuple can be easily found
# (Basically functions which make it act like a dictionary with multiple keys for each tuple.)


class FanacNames:
    def __init__(self):
        pass

    # ----------------------------------------------------------------------------------
    # Do a case-insenstive compare which also treates "The xxx" and "xxx, The" as the same
    def CompareNames(self, name1, name2):
        if name1 == None or name2 == None:
            return False

        if name1.lower().startswith("the "):
            name1=name1[4:].strip()
        if name1.lower().endswith(", the"):
            name1=name1[:-5].strip()

        if name2.lower().startswith("the "):
            name2=name2[4:].strip()
        if name2.lower().endswith(", the"):
            name2=name2[:-5].strip()

        if name1.lower().startswith("a "):
            name1=name1[2:].strip()
        if name1.lower().endswith(", a"):
            name1=name1[:-3].strip()

        if name2.lower().startswith("a "):
            name2=name2[2:].strip()
        if name2.lower().endswith(", a"):
            name2=name2[:-3].strip()

        if name1.lower().startswith("an "):
            name1=name1[3:].strip()
        if name1.lower().endswith(", an"):
            name1=name1[:-4].strip()

        if name2.lower().startswith("an "):
            name2=name2[3:].strip()
        if name2.lower().endswith(", an"):
            name2=name2[:-4].strip()

        return Helpers.CompressName(name1) == Helpers.CompressName(name2)


    #======================================================================
    # Given a Retro_Name create a new tuple if needed or add it to an existing tuple
    def AddRetroName(self, name):
        if len(g_fanacNameTuples)> 0:
            for t in g_fanacNameTuples:
                if t.RetroName == name:
                    return  # Nothing to do -- it's already in there.

        # Now we check to see if a matching name is in it that has a blank RetroName.
        for i in range(0, len(g_fanacNameTuples)):
            if self.CompareNames(g_fanacNameTuples[i].FanacStandardName, name):
                g_fanacNameTuples[i]=g_fanacNameTuples[i]._replace(RetroName=name)
                return

        # Nothing. So the last recoruse is simply to add a new tuple.
        g_fanacNameTuples.append(FanacNameXYZ(JoesName=None, FanacStandardName=None, DisplayName=None, RetroName=name))
        return

    #========================================================
    # Add the fanac directory dictionary to the names list
    def AddFanacDirectories(self, fanacDirs):
        if fanacDirs == None or len(fanacDirs) == 0:
            print("***AddFanacDirectories tried to add an empty FanacOrgReaders.fanacDirectories")
            return

        # This is being done to initialize fanacNameTuples, so make sure it';s empty
        if g_fanacNameTuples != None and len(g_fanacNameTuples) > 0:
            print("***AddFanacDirectories tried to initialize an non-empty fanacNameTuples")
            return

        for name, dir in fanacDirs.items():
            g_fanacNameTuples.append(FanacNameXYZ(JoesName=None, DisplayName=None, FanacStandardName=name, RetroName=None))

        return


    #=====================================================================
    # This checks for an exact match of the Fanac Standard name
    def ExistsFanacStandardName(self, name):
        for nt in g_fanacNameTuples:
            if nt.FanacStandardName.lower() == name.lower():
                return True
        return False


    #=====================================================================
    # This checks for an exact match of the Fanac Standard name
    def LocateFanacStandardName(self, name):
        for i in range(0, len(g_fanacNameTuples)):
            if g_fanacNameTuples[i].FanacStandardName.lower() == name.lower():
                return i
        return None



    #======================================================================
    # Given a Fanac Standard fanzine name create a new tuple if needed or add it to an existing tuple
    def AddFanzineStandardName(self, name):
        #
        # if len(fanacNameTuples) == 0:
        #     fanacNameTuples=FanacName(None, None, None, name, None)
        #     return fanacNameTuples

        for t in g_fanacNameTuples:
            if t.FanacStandardName == name:
               return g_fanacNameTuples

        g_fanacNameTuples.append(FanacNameXYZ(JoesName=None, DisplayName=None, FanacStandardName=name, RetroName=None))
        return


    #==========================================================================
    # Convert a name to standard by lookup
    def StandardizeName(self, name):

        # First handle the location of the "The"
        if name[0:3] == "The ":
            name=name[4:]+", The"

        # First see if it is in the list of standard names
        for nt in g_fanacNameTuples:
            if nt.FanacStandardName != None and Helpers.CompareCompressedName(nt.FanacStandardName, name):
                return nt.FanacStandardName

        # Now check other forms.
        for nt in g_fanacNameTuples:
            if nt.RetroName != None and Helpers.CompareCompressedName(nt.RetroName, name):
                if nt.FanacStandardName != None:
                    return nt.FanacStandardName
                else:
                    return "StandardizeName("+name+") failed"

        for nt in g_fanacNameTuples:
            if nt.JoesName != None and Helpers.CompareCompressedName(nt.JoesName, name):
                if nt.FanacStandardName != None:
                    return nt.FanacStandardName
                else:
                    return "StandardizeName("+name+") failed"

        for nt in g_fanacNameTuples:
            if nt.DisplayName != None and Helpers.CompareCompressedName(nt.DisplayName, name):
                if nt.FanacStandardName != None:
                    return nt.FanacStandardName
                else:
                    return "StandardizeName("+name+") failed"
        return "StandardizeName("+name+") failed"

# ----------------------------------------------------------
# Take a fanzine title string and try to capitalize it correctly
def CapitalizeFanzine(name):

    # Start by putting the name in title case.
    name=name.title()

    # Now de-capitalize some words
    name=name.replace(" Of ", " of ").replace(" The ", " the ").replace(" In ", " in ").replace( "And ", " and ")

    # Deal with an odd limitation of title() where it leaves possessive 'S capitalized (e.g., "Milty'S Mag")
    name=name.replace("'S ", "'s ").replace("’S ", "’s ")

    return name