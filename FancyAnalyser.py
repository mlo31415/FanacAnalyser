import collections
import re
import Helpers
import FanacNames
import FanacOrgReaders
import FanacDirectories
import IssueSpec

#--------------------------------------
# Overall Strategy
# (1) Read fanac.org's fanzine index pages to get a list of all the fanzines represented including name and directory name.  (We don't at this time read the actual data.)
#       FanacOrgReaders.ReadClassicModernPages()
# (2) Read Joe's list of all 1942 fanzines.  This includes information on what fanzines are eligible for the 1942 Retro Hugo
#   We add those names to the fanzine dictionary, also.
#   We create a list of all 1942 fanzines including issue info.
#       allFanzines1942=RetroHugoReaders.Read1942FanzineList()
# (3) Read a list of links to individual fanzines not on fanac.org
#       Done in code when ExternalLinks class is instantiated
# (4) Go through the fanzines directories on fanac.org, and get a list of issues present, including the links to the scans
#     This also loads the table of fanac.org directory index.html types
#       FanacOrgReaders.ReadFanacFanzineIssues(FanacOrgReaders.g_FanacDirectories)
# (5) Combine the information into a single grand table of fanzines which includes links to the issues
# (6) Go through Joe's list and try to interpret the issue designations and match them with other sources
# (7) Generate the output HTML
#--------------------------------------

# Create the list of FanacName tuples which will be used by FanacName functions
# Note: This is just to get the names and directories, nothing else.
FanacDirectories.FanacDirectories().Dict()
#FanacNames.FanacNames().AddFanacDirectories(FanacDirectories.FanacDirectories().Dict())      # Add them to g_fanacNameTuples, which is managed and accessed by FanacNames

# Read Joe's PDF and create a list of tuples, each representing one of the complete set of fanzines of 1942
# The three items of the tuple are the fanzine name, the fanzine editors, andf the fanzine issue data.
# Some of this is pretty rough, being taken from somewhat inconsistant text in the PDF.
# This will also add any new names found to the FanacNames tuples
#allFanzines1942=RetroHugoReaders.Read1942FanzineList()

# Read the fanac.org fanzine direcgtory and produce a lost of all issues present
FanacOrgReaders.ReadFanacFanzineIssues()

# Print list of all fanzines found
from operator import itemgetter
FanacOrgReaders.g_fanacIssueInfo.sort(key=lambda elem: elem.MonthInt)  # Sorts in place on month
FanacOrgReaders.g_fanacIssueInfo.sort(key=lambda elem: elem.YearInt)  # Sorts in place on year
FanacOrgReaders.g_fanacIssueInfo.sort(key=lambda elem: elem.FanzineIssueName)  # Sorts in place on fanzine name
for fz in FanacOrgReaders.g_fanacIssueInfo:
    if fz.Year == 1943:
        print(str(fz))

file=open("1943 Fanzines.txt", "w+")
for fz in FanacOrgReaders.g_fanacIssueInfo:
    if fz.YearInt == 1943:
        file.write(fz.FanzineIssueName+"\n")
file.close()

i=0