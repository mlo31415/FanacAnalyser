import Helpers
import FanacOrgReaders
import requests
from bs4 import BeautifulSoup


Helpers.LogOpen("Fanac Analysis Log.txt", "Fanac Error Log.txt")

# ====================================================================================
# Read fanac.org/fanzines/Classic_Fanzines.html amd /Modern_Fanzines.html
# Read the table to get a list of all the fanzines on Fanac.org
# Return a list of tuples (name on page, name of directory)
#       The name on page is the display named used in the Classic and Modern tables
#       The name of directory is the name of the directory pointed to

def ReadClassicModernPages():
    print("----Begin reading Classic and Modern tables")
    # This is a dictionary of fanzines on Fanac.org
    # The key is the compressed name (Helpers.CompressName())
    # The value is a tuple consisting of the link name and link url
    fanacFanzineDirectories={}

    ReadModernOrClassicTable(fanacFanzineDirectories, "http://www.fanac.org/fanzines/Classic_Fanzines.html")
    ReadModernOrClassicTable(fanacFanzineDirectories, "http://www.fanac.org/fanzines/Modern_Fanzines.html")
    ReadModernOrClassicTable(fanacFanzineDirectories, "http://www.fanac.org/fanzines/Electronic_Fanzines.html")

    print("----Done reading Classic and Modern tables")
    return fanacFanzineDirectories

# -------------------------------------------------------------------------
# We have a name and a dirname from the fanac.org Classic and Modern pages.
# The dirname *might* be a URL in which case it needs to be handled as a foreign directory reference
def AddFanacDirectory(fanacFanzineDirectories, name, dirname):
    isDup=False

    if name in fanacFanzineDirectories:
        print("   duplicate: name="+name+"  dirname="+dirname)
        return

    if dirname[:3]=="http":
        print("    ignored, because is HTML: "+dirname)
        return

    # Add name and directory reference
    cname=Helpers.CompressName(name)
    print("   added to fanacFanzineDirectories: key='"+cname+"'  name='"+name+"'  dirname='"+dirname+"'")
    fanacFanzineDirectories[cname]=(name, dirname)
    return

# ======================================================================
def ReadModernOrClassicTable(fanacFanzineDirectories, url):
    h=requests.get(url)
    s=BeautifulSoup(h.content, "html.parser")
    # We look for the first table that does not contain a "navbar"
    tables=s.find_all("table")
    for table in tables:
        if "sortable" in str(table.attrs) and not "navbar" in str(table.attrs):
            # OK, we've found the main table.  Now read it
            trs=table.find_all("tr")
            for i in range(1, len(trs)):
                # Now the data rows
                name=trs[i].find_all("td")[1].contents[0].contents[0].contents[0]
                dirname=trs[i].find_all("td")[1].contents[0].attrs["href"][:-1]
                AddFanacDirectory(fanacFanzineDirectories, name, dirname)
    return

# Read the fanac.org fanzine directory and produce a list of all issues present
fanacFanzineDirectories=ReadClassicModernPages()
fanacIssueList=FanacOrgReaders.ReadFanacFanzineIssues(fanacFanzineDirectories)


Helpers.LogClose()

# Print a list of all fanzines found for 1943 sorted by fanzine name, then date
fanacIssueList.sort(key=lambda elem: elem.MonthInt)  # Sorts in place on month
fanacIssueList.sort(key=lambda elem: elem.YearInt)  # Sorts in place on year
fanacIssueList.sort(key=lambda elem: elem.FanzineIssueName)  # Sorts in place on fanzine name

file=open("1943 Fanzines.txt", "w+")
count1943=0
for fz in fanacIssueList:
    if fz.YearInt == 1943:
        file.write(fz.FanzineIssueName+"\n")
        count1943=count1943+1
file.close()

# Get a count of issues and pages
pageCount=0
issueCount=0
for fz in fanacIssueList:
    if fz.URL != None:
        pageCount=pageCount+fz.Pages
        issueCount=issueCount+1

# Produce a list of fanzines by date
fanacIssueList.sort(key=lambda elem: elem.DayInt)  # Sorts in place on day
fanacIssueList.sort(key=lambda elem: elem.MonthInt)  # Sorts in place on month
fanacIssueList.sort(key=lambda elem: elem.YearInt)  # Sorts in place on year

f=open("Chronological Listing of Fanzines.txt", "w+")
monthYear=(-1, -1)
for fz in fanacIssueList:
    if fz.URL is not None:
        if monthYear != (fz.MonthInt, fz.YearInt):
            f.write("\n"+ str(fz.YearInt)+" "+str(fz.MonthInt)+"\n")
            monthYear=(fz.MonthInt, fz.YearInt)
        f.write("   "+fz.FanzineIssueName+"\n")
f.close()

# Generate html for a chronological table
f=open("Chronological Listing of Fanzines.html", "w+")
f.write('<table border="2" cellspacing="4">\n') # Begin the main table

monthYear=""
for fz in fanacIssueList:
    if fz.URL is None  or fz.YearInt == 0:
        continue

    # Start the row
    # Put the month & year in the first column of the table only if it changes.
    month=fz.MonthInt
    if month == 0:
        month=1
    newMonthYear= Helpers.IntToMonth(month) + " " + str(fz.YearInt)
    if newMonthYear != monthYear:
        if monthYear != "":   # Is this the first month box?
            f.write('</table></td></tr>\n')  # No.  So end the previous month box

        f.write('<tr><td><table>')    # Start a new month box
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