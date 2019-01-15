import Helpers
import FanacOrgReaders
import requests
from bs4 import BeautifulSoup
import FanacDates

Helpers.LogOpen("Fanac Analysis Log.txt", "Fanac Error Log.txt")

# ====================================================================================
# Read fanac.org/fanzines/Classic_Fanzines.html amd /Modern_Fanzines.html
# Read the table to get a list of all the fanzines on Fanac.org
# Return a list of tuples (name on page, name of directory)
#       The name on page is the display named used in the Classic and Modern tables
#       The name of directory is the name of the directory pointed to

def ReadClassicModernPages():
    print("----Begin reading Classic and Modern tables")
    # This is a list of fanzines on Fanac.org
    # Each item is a tuple of (compressed name,  link name,  link url)
    fanacFanzineDirectories=[]
    directories=Helpers.ReadList("control-topleveldirectories.txt")
    for dirs in directories:
        ReadModernOrClassicTable(fanacFanzineDirectories, dirs)

    print("----Done reading Classic and Modern tables")
    return fanacFanzineDirectories


# ======================================================================
# Read one of the main fanzine directory listings and append all the fanzines directories found to the dictionary
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


#================================================================================
# Generate html for a chronological table
def WriteHTMLFile(name, fanacIssueList, selector):
    f=open(name, "w+")
    f.write('<table border="2" cellspacing="4">\n')  # Begin the main table
    monthYear=""
    for fz in fanacIssueList:
        if fz.URL is None or fz.Date.YearInt == 0:
            continue

        if selector is not None and not selector(fz):
            continue

        # Start the row
        # Put the month & year in the first column of the table only if it changes.
        month=fz.Date.MonthInt
        if month == 0:
            month=1
        newMonthYear=FanacDates.FormatDate2(fz.Date.YearInt, month, None)
        if newMonthYear != monthYear:
            if monthYear != "":  # Is this the first month box?
                f.write('</table></td></tr>\n')  # No.  So end the previous month box

            f.write('<tr><td><table>')  # Start a new month box
            monthYear=newMonthYear
            f.write('    <tr><td width="120">\n'+newMonthYear+'</td>\n')
        else:
            f.write('    <tr><td width="120">&nbsp;</td>\n')  # Add an empty month box

        # The hyperlink goes in column 2
        # There are two kinds of hyperlink: Those with just a filename (xyz.html) and those with a full URL (http://xxx.vvv.zzz.html)
        # The former are easy, but the latter need to be processed
        if "/" not in fz.URL:
            url=fz.DirectoryURL+"/"+fz.URL
        else:
            # There are two possibilities: This is a reference to somewhere else in fanzines or this is a reference elsewhere.
            # If it is in fanzines, then the url ends with <stuff>/fanzines/<dir>/<file>.html
            parts=fz.URL.split("/")
            if len(parts) > 2 and parts[-3:-2][0] == "fanzines":
                url=fz.DirectoryURL+"/../"+"/".join(parts[-2:])
            else:
                url=fz.URL

        f.write('        <td width="250">'+'<a href="'+url+'">'+fz.FanzineIssueName+'</a>'+'</td>\n')

        # And end the row
        f.write('  </tr>\n')
    f.write("</table></td></tr>\n")
    f.write('</table>\n')
    f.close()


#================================================================================
# Header, headerText and bodyText are all lambdas
#   header is the item used to decide when to start a new subsection
#   headerText is used to title the subsection
#   bodyText is what is listed in the subsection
def WriteTextFile(filename, fanacIssueList, headerText, bodyText):
    f=open(filename, "w+")
    lastHeader=None
    for fz in fanacIssueList:
        if fz.URL is not None:
            if lastHeader != headerText(fz):
                f.write("\n"+ headerText(fz)+"\n")
                lastHeader=headerText(fz)
            f.write("   "+bodyText(fz)+"\n")
    f.close()


# -------------------------------------------------------------------------
# We have a name and a dirname from the fanac.org Classic and Modern pages.
# The dirname *might* be a URL in which case it needs to be handled as a foreign directory reference
def AddFanacDirectory(fanacFanzineDirectories, name, dirname):
    isDup=False

    # We don't want to add duplicates. A duplicate is one which has the same dirname, even if the text pointing to it is different.
    dups=[e2 for e1, e2 in fanacFanzineDirectories if e2 == dirname]
    if len(dups) > 0:
        print("   duplicate: name="+name+"  dirname="+dirname)
        return

    if dirname[:3]=="http":
        print("    ignored, because is HTML: "+dirname)
        return

    # Add name and directory reference
    print("   added to fanacFanzineDirectories:  name='"+name+"'  dirname='"+dirname+"'")
    fanacFanzineDirectories.append((name, dirname))
    return


# Read the fanac.org fanzine directory and produce a list of all issues present
fanacFanzineDirectories=ReadClassicModernPages()
fanacIssueList=FanacOrgReaders.ReadFanacFanzineIssues(fanacFanzineDirectories)

Helpers.LogClose()

# Print a list of all fanzines found for 1943 sorted by fanzine name, then date
fanacIssueList.sort(key=lambda elem: elem.Date)
fanacIssueList.sort(key=lambda elem: elem.FanzineIssueName.lower())  # Sorts in place on fanzine name

def NoNone(str):
    if str is None:
        return ""
    return str

file=open("control-1943 fanac.org Fanzines.txt", "w+")
count1943=0
for fz in fanacIssueList:
    if fz.Date.YearInt == 1943:
        file.write("|| "+NoNone(fz.FanzineIssueName)+" || "+NoNone(fz.Date.FormatDate())+" || " + NoNone(fz.DirectoryURL) +" || " + NoNone(fz.URL) + " ||\n")
        count1943=count1943+1
file.close()

# Get a count of issues and pages
pageCount=0
issueCount=0
f=open("Test - Items with No Page Count.txt", "w+")
for fz in fanacIssueList:
    if fz.URL != None:
        pageCount=pageCount+(fz.Pages if fz.Pages > 0 else 1)
        issueCount=issueCount+1
        if fz.Pages == 0:
            f.write(fz.FanzineName+"  "+fz.Serial.FormatSerial()+"\n")
f.close()

# Produce a list of fanzines listed by date
fanacIssueList.sort(key=lambda elem: elem.Date)

WriteTextFile("Chronological Listing of Fanzines.txt", fanacIssueList, lambda fz: FanacDates.FormatDate2(fz.Date.YearInt, fz.Date.MonthInt, None), lambda fz: fz.FanzineIssueName)
WriteHTMLFile("Chronological Listing of Fanzines.html", fanacIssueList, None)

# Get the names of the newszines as a list
listOfNewszines=Helpers.ReadList("control-newszines.txt")
listOfNewszines=[x.lower() for x in listOfNewszines]  # Need strip() to get rid of trailing /n (at least)

nonNewszines=[fx.FanzineName.lower() for fx in fanacIssueList if fx.FanzineName.lower() not in listOfNewszines]
nonNewszines=sorted(list(set(nonNewszines)))

newszines=[fx.FanzineName.lower() for fx in fanacIssueList if fx.FanzineName.lower() in listOfNewszines]
newszines=sorted(list(set(newszines)))

unusedLines=[x for x in listOfNewszines if x.lower() not in newszines]
unusedLines=[x+"\n" for x in unusedLines]

newszines=[x+"\n" for x in newszines]
with open("Test - Newszines.txt", "w+") as f:
    f.writelines(newszines)
with open("Test - Unused lines.txt", "w+") as f:
    f.writelines(unusedLines)
nonNewszines=[x+"\n" for x in nonNewszines]
with open("Test - Non-newzines.txt", "w+") as f:
    f.writelines(nonNewszines)

WriteHTMLFile("Chronological Listing of Newszines.html", fanacIssueList, lambda fx: fx.FanzineName.lower() in listOfNewszines)

# Produce a list of fanzines by title
fanacIssueList.sort(key=lambda elem: elem.Date)  # Sorts in place on Date
fanacIssueList.sort(key=lambda elem: elem.FanzineName.lower())  # Sorts in place on fanzine's name
WriteTextFile("Alphabetical Listing of Fanzines.txt", fanacIssueList, lambda fz: fz.FanzineName, lambda fz: fz.FanzineIssueName+":   "+fz.Date.FormatDate())

print("\n")
print("Issues: "+str(issueCount)+"  Pages: "+str(pageCount))
print("1943 Fanzines: "+str(count1943))