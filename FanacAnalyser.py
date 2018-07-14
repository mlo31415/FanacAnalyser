import collections
import FanacOrgReaders
import FanacDirectories


logFile=open("FanacAnalysisLog.txt", "w+")

# Trigger the reading of the fanac fanzine directories
FanacDirectories.FanacDirectories()

# Read the fanac.org fanzine direcgtory and produce a list of all issues present
FanacOrgReaders.ReadFanacFanzineIssues(logFile)

logFile.close()

# Print list of all fanzines found
FanacOrgReaders.g_fanacIssueInfo.sort(key=lambda elem: elem.MonthInt)  # Sorts in place on month
FanacOrgReaders.g_fanacIssueInfo.sort(key=lambda elem: elem.YearInt)  # Sorts in place on year
FanacOrgReaders.g_fanacIssueInfo.sort(key=lambda elem: elem.FanzineIssueName)  # Sorts in place on fanzine name
for fz in FanacOrgReaders.g_fanacIssueInfo:
    if fz.YearInt == 1943:
        print(str(fz))

file=open("1943 Fanzines.txt", "w+")
for fz in FanacOrgReaders.g_fanacIssueInfo:
    if fz.YearInt == 1943:
        file.write(fz.FanzineIssueName+"\n")
file.close()

# Get a count of issues and pages
pageCount=0
issueCount=0
for fz in FanacOrgReaders.g_fanacIssueInfo:
    if fz.URL != None:
        pageCount=pageCount+fz.Pages
        issueCount=issueCount+1

print("Issue: "+str(issueCount)+"  Pages: "+str(pageCount))