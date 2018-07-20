import Helpers
import FanacOrgReaders
import FanacDirectories


logFile=open("FanacAnalysisLog.txt", "w+")

# Trigger the reading of the fanac fanzine directories
FanacDirectories.FanacDirectories()

# Read the fanac.org fanzine direcgtory and produce a list of all issues present
FanacOrgReaders.ReadFanacFanzineIssues(logFile)

logFile.close()

# Print a list of all fanzines found for 1943
FanacOrgReaders.g_fanacIssueInfo.sort(key=lambda elem: elem.MonthInt)  # Sorts in place on month
FanacOrgReaders.g_fanacIssueInfo.sort(key=lambda elem: elem.YearInt)  # Sorts in place on year
FanacOrgReaders.g_fanacIssueInfo.sort(key=lambda elem: elem.FanzineIssueName)  # Sorts in place on fanzine name

file=open("1943 Fanzines.txt", "w+")
count1943=0
for fz in FanacOrgReaders.g_fanacIssueInfo:
    if fz.YearInt == 1943:
        file.write(fz.FanzineIssueName+"\n")
        count1943=count1943+1
file.close()

# Get a count of issues and pages
pageCount=0
issueCount=0
for fz in FanacOrgReaders.g_fanacIssueInfo:
    if fz.URL != None:
        pageCount=pageCount+fz.Pages
        issueCount=issueCount+1

# Produce a list of fanzines by date
FanacOrgReaders.g_fanacIssueInfo.sort(key=lambda elem: elem.DayInt)  # Sorts in place on day
FanacOrgReaders.g_fanacIssueInfo.sort(key=lambda elem: elem.MonthInt)  # Sorts in place on month
FanacOrgReaders.g_fanacIssueInfo.sort(key=lambda elem: elem.YearInt)  # Sorts in place on year

f=open("Chronological Listing of Fanzines.txt", "w+")
monthYear=(-1, -1)
for fz in FanacOrgReaders.g_fanacIssueInfo:
    if fz.URL is not None:
        if monthYear != (fz.MonthInt, fz.YearInt):
            f.write("\n"+ str(fz.YearInt)+" "+str(fz.MonthInt)+"\n")
            monthYear=(fz.MonthInt, fz.YearInt)
        f.write("   "+fz.FanzineIssueName+"\n")
f.close()

# Generate html for a chronological table
f=open("Chronological Listing of Fanzines.html", "w+")
f.write('<table border="0" cellspacing="7">\n') # Begin the main table

monthYear=""
for fz in FanacOrgReaders.g_fanacIssueInfo:
    if fz.URL is None  or fz.YearInt == 0:
        continue

    # Start the row
    # Put the month & year in the first column of the table only if it changes.
    newMonthYear= Helpers.IntToMonth(fz.MonthInt) + " " + str(fz.YearInt)
    if newMonthYear != monthYear:
        if monthYear != "":   # Is this the first month box?
            f.write('</table></td></tr>\n')  # No.  So end the previous month box

        f.write('<tr><td><table border="0">')    # Start a new month box
        monthYear=newMonthYear
        f.write('    <tr><td width="120">\n' + newMonthYear + '</td>\n')
    else:
        f.write('    <tr><td width="120">&nbsp;</td>\n')        # Add an empty month box

    # The hyperlink goes in column 2
    url=fz.DirectoryURL+"/"+fz.URL
    f.write('        <td width="250">' + '<a href="'+url+'">'+fz.FanzineIssueName+'</a>' + '</td>\n')

    # And end the row
    f.write('  </tr>\n')

f.write("</table></td></tr>\n")
f.write('</table>\n')
f.close()


print("\n")
print("Issues: "+str(issueCount)+"  Pages: "+str(pageCount))
print("1943 Fanzines: "+str(count1943))