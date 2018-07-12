import collections
import FanacOrgReaders
import FanacDirectories


# Trigger the reading of the fanac fanzine directories
FanacDirectories.FanacDirectories()

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