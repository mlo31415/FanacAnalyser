import Helpers
import FanacOrgReaders
import requests
from bs4 import BeautifulSoup
import os
import FanacDates
from tkinter import *
from tkinter import messagebox

Helpers.LogOpen("Log - Fanac Analyzer Detailed Analysis Log.txt", "Log - Fanac Analyzer Error Log.txt")

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
# fRowHeaderText and fRowBodyText and fSelector are all lambdas
#   fSelector decides if this fanzines is to be listed and returns True for fanzines to be listed, and False for ones to be skipped. (If None, nothing will be skipped)
#   fRowHeaderText and fRowBodyText are functions which pull information out of a fanzineIssue from fanzineIssueList
#   fRowHeaderText is the item used to decide when to start a new subsection
#   fRowBodyText is what is listed in the subsection
def WriteTable(filename, fanacIssueList, fRowHeaderText, fRowBodyText, headerText, isDate=True, fSelector=None):
    f=open(filename, "w+")

    # Filename can end in ".html" or ".txt" and we output html or plain text accordingly
    html=os.path.splitext(filename)[1].lower() == ".html"
    if html:
        try:
            with open("control-Header.html", "r") as f2:
                f.writelines(f2.readlines())
        except:
            pass    # Except nothing, really.  If the file's not there, we ignore the whole thing.

    if headerText is not None:
        if html:
            headerText="<p>"+headerText+"<p>"
        f.write(headerText)


    # If we have an HTML header, we need to create a set of jump buttons.
    # If it's alpha, the buttons are by 1st letter; if date it's by decade
    # First, we determine the potential button names.  There are two choices: Letters of the alphabet or decades
    if html:
        headers=set()
        for fz in fanacIssueList:
            if fRowHeaderText is not None:
                if isDate:
                    headers.add(fRowHeaderText(fz)[-4:-1]+"0s")
                else:
                    headers.add(fRowHeaderText(fz)[:1])

        headerlist=list(headers)
        headerlist.sort()
        buttonlist=""
        for item in headerlist:
            if len(buttonlist) > 0:
                buttonlist=buttonlist+" -- "
            buttonlist=buttonlist+'<a href="#' + item + '">' + item + '</a>'

        # Write out the button bar
        f.write(buttonlist+"<p><p>")

    # Start the table if this is HTML
    if html:
        f.write('<table border="2" cellspacing="4">\n')  # Begin the main table

    lastRowHeader=None
    lastBLS=None
    for fz in fanacIssueList:
        # Do we skip this fanzine
        if fSelector is not None and not fSelector(fz):
            continue
        if html and fz.URL is None:
            continue

        # Get the button link string
        bls=""
        if html:
            if fRowHeaderText is not None:
                if isDate:
                    bls=fRowHeaderText(fz)[-4:-1]+"0s"
                else:
                    bls=fRowHeaderText(fz)[:1]

        # Deal with Column 1
        if fRowHeaderText is not None and lastRowHeader != fRowHeaderText(fz):
            if lastRowHeader is not None:  # Is this the first sub-box?
                if html: f.write('</table></td></tr>\n')  # No.  So we must end the previous sub-box

            if html: f.write('<tr><td><table>')  # Start a new sub-box
            lastRowHeader=fRowHeaderText(fz)
            # Since this is a new sub-box, we write the header in col 1
            if html:
                f.write('    <tr><td width="120">\n'+lastRowHeader)
                if bls != lastBLS:
                    f.write('<a name="'+bls+'"></a>')
                    lastBLS=bls
                f.write('</td>\n')
            else:
                f.write("\n"+fRowHeaderText(fz)+"\n")
        else:
            # Otherwise, we put an empty cell there
            if html: f.write('    <tr><td width="120">&nbsp;</td>\n')  # Add an empty sub-box

        # Deal with Column 2
        # The hyperlink goes in column 2
        # There are two kinds of hyperlink: Those with just a filename (xyz.html) and those with a full URL (http://xxx.vvv.zzz.html)
        # The former are easy, but the latter need to be processed
        if html:
            if "/" not in fz.URL:
                url=fz.DirectoryURL+"/"+fz.URL
            else:
                # There are two possibilities: This is a reference to somewhere in the fanzines directory or this is a reference elsewhere.
                # If it is in fanzines, then the url ends with <stuff>/fanzines/<dir>/<file>.html
                parts=fz.URL.split("/")
                if len(parts) > 2 and parts[-3:-2][0] == "fanzines":
                    url=fz.DirectoryURL+"/../"+"/".join(parts[-2:])
                else:
                    url=fz.URL
            f.write('        <td width="350">'+'<a href="'+url+'">'+fz.FanzineIssueName+'</a>'+'</td>\n')
        else:
            f.write("   "+fRowBodyText(fz)+"\n")

        # And end the row
        if html: f.write('  </tr>\n')

    # And end everything
    if html:
        f.write("</table></td></tr>\n")
        f.write('</table>\n')
        try:
            with open("control-Footer.html", "r") as f2:
                f.writelines(f2.readlines())
        except:
            pass  # Except nothing, really.  If the file's not there, we ignore the whole thing.
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


#===========================================================================
#===========================================================================
# Main

# Read the command line arguments
outputDir="."
if len(sys.argv) > 1:
    outputDir=sys.argv[1]
if not os.path.isdir(outputDir):
    os.mkdir(outputDir)
if not os.path.isdir(os.path.join(outputDir, "Reports")):
    os.mkdir(os.path.join(outputDir, "Reports"))
if not os.path.isdir(os.path.join(outputDir, "Test")):
    os.mkdir(os.path.join(outputDir, "Test"))

# Read the fanac.org fanzine directory and produce a list of all issues and all newszines present
fanacFanzineDirectories=ReadClassicModernPages()
(fanacIssueList, newszinesFromH2)=FanacOrgReaders.ReadFanacFanzineIssues(fanacFanzineDirectories)

# Print a list of all fanzines sorted by fanzine name, then date
fanacIssueList.sort(key=lambda elem: elem.Date)
fanacIssueList.sort(key=lambda elem: elem.FanzineIssueName.lower())  # Sorts in place on fanzine name

def NoNone(str):
    if str is None:
        return ""
    return str


# Read the control-year.txt file to get the year to be dumped out
text=Helpers.ReadList("control-year.txt")
selectedYear=Helpers.InterpretNumber(text[0])

file=open(os.path.join(outputDir, "Reports", str(selectedYear)+" fanac.org Fanzines.txt"), "w+")
countSelectedYear=0
for fz in fanacIssueList:
    if fz.Date.YearInt == selectedYear:
        file.write("|| "+NoNone(fz.FanzineIssueName)+" || "+NoNone(fz.Date.FormatDate())+" || " + NoNone(fz.DirectoryURL) +" || " + NoNone(fz.URL) + " ||\n")
        countSelectedYear+=1
file.close()

# Get a count of issues, pdfs, and pages
pageCount=0
issueCount=0
pdfCount=0
f=open(os.path.join(outputDir, "Reports", "Items (not PDFs) with No Page Count.txt"), "w+")
for fz in fanacIssueList:
    if fz.URL != None:
        issueCount+=1
        if os.path.splitext(fz.URL)[1] == ".pdf":
            pdfCount+=1
            pageCount+=1
        else:
            pageCount+=(fz.Pages if fz.Pages > 0 else 1)
            if fz.Pages == 0:
                f.write(fz.FanzineName+"  "+fz.Serial.FormatSerial()+"\n")
f.close()

# Produce a list of fanzines listed by date
fanacIssueList.sort(key=lambda elem: elem.FanzineIssueName.lower(), reverse=True)  # Sorts in place on fanzine's name
fanacIssueList.sort(key=lambda elem: elem.Date)
undatedList=[f for f in fanacIssueList if f.Date.IsEmpty()]
datedList=[f for f in fanacIssueList if not f.Date.IsEmpty()]

headerText=str(issueCount)+" issues consisting of "+str(pageCount)+" pages."
WriteTable(os.path.join(outputDir, "Chronological Listing of Fanzines.html"),
           datedList,
           lambda fz: FanacDates.FormatDate2(fz.Date.YearInt, fz.Date.MonthInt, None),
           lambda fz: fz.FanzineIssueName,
           headerText)
WriteTable(os.path.join(outputDir, "Chronological Listing of Fanzines.txt"),
           datedList,
           lambda fz: FanacDates.FormatDate2(fz.Date.YearInt, fz.Date.MonthInt, None),
           lambda fz: fz.FanzineIssueName,
           headerText)
WriteTable(os.path.join(outputDir, "Reports", "Undated Fanzine Issues.html"),
           undatedList,
           None,
           lambda fz: fz.FanzineIssueName,
           headerText)

# Get the names of the newszines as a list
listOfNewszines=Helpers.ReadList("control-newszines.txt")
listOfNewszines=[x.lower() for x in listOfNewszines]  # Need strip() to get rid of trailing /n (at least)

# Now add in the newszines discovered in the <h2> blocks
listOfNewszines=listOfNewszines+newszinesFromH2

# This results in a lot of duplication.  Get rid of duplicates by turning listOfNewszines into a set and back again.
# Note that this scrambles the order.
listOfNewszines=list(set(listOfNewszines))

nonNewszines=[fx.FanzineName.lower() for fx in fanacIssueList if fx.FanzineName.lower() not in listOfNewszines]
nonNewszines=sorted(list(set(nonNewszines)))

newszines=[fx.FanzineName.lower() for fx in fanacIssueList if fx.FanzineName.lower() in listOfNewszines]
newszines=sorted(list(set(newszines)))

# Count the number of issue and pages of all fanzines and just newszines
newsPageCount=0
newsIssueCount=0
newsPdfCount=0
for fz in fanacIssueList:
    if fz.FanzineName in listOfNewszines and fz.URL != None:
        newsIssueCount+=1
        if os.path.split(fz.URL)[1].lower() == ".pdf":
            newsPdfCount+=1
            newsPageCount+=1
        else:
            newsPageCount+=(fz.Pages if fz.Pages > 0 else 1)

# Look for lines in the list of newszines which don't match actual newszines ont he site.
unusedLines=[x for x in listOfNewszines if x.lower() not in newszines]
unusedLines=[x+"\n" for x in unusedLines]

newszines=[x+"\n" for x in newszines]
with open(os.path.join(outputDir, "Test", "Newszines.txt"), "w+") as f:
    f.writelines(newszines)
with open(os.path.join(outputDir, "Test", "Unused lines in newszines.txt"), "w+") as f:
    f.writelines(unusedLines)
nonNewszines=[x+"\n" for x in nonNewszines]
with open(os.path.join(outputDir, "Test", "Non-newszines.txt"), "w+") as f:
    f.writelines(nonNewszines)

newszinesFromH2=[x+"\n" for x in newszinesFromH2]
with open(os.path.join(outputDir, "Test", "Newzsines found by H2 tags.txt"), "w+") as f:
    f.writelines(newszinesFromH2)

headerText=str(newsIssueCount)+" issues consisting of "+str(newsPageCount)+" pages."
WriteTable(os.path.join(outputDir, "Chronological Listing of Newszines.html"),
           fanacIssueList,
           lambda fz: FanacDates.FormatDate2(fz.Date.YearInt, fz.Date.MonthInt, None),
           lambda fz: fz.FanzineIssueName,
           headerText,
           fSelector=lambda fx: fx.FanzineName.lower() in listOfNewszines)

# Produce a list of fanzines by title
headerText=str(issueCount)+" issues consisting of "+str(pageCount)+" pages."
fanacIssueList.sort(key=lambda elem: elem.Date)  # Sorts in place on Date
fanacIssueList.sort(key=lambda elem: elem.FanzineName.lower())  # Sorts in place on fanzine's name
WriteTable(os.path.join(outputDir, "Alphabetical Listing of Fanzines.txt"),
           fanacIssueList,
           lambda fz: fz.FanzineName,
           lambda fz: fz.FanzineIssueName,
           headerText,
           isDate=False)
WriteTable(os.path.join(outputDir, "Alphabetical Listing of Fanzines.html"),
           fanacIssueList,
           lambda fz: fz.FanzineName,
           lambda fz: fz.FanzineIssueName,
           headerText,
           isDate=False)

def RemoveArticles(name):
    if name[:4] == "The ":
        return name[4:]
    if name[:2] == "a ":
        return name[2:]
    # It's harder to find a trailing ', The'
    if name.find(", The") > 0:
        return name.replace(", The", "")
    return name

# Read through the alphabetic list and generate a flag file of cases where the issue name doesn't match the serial name
def OddNames(n1, n2):
    n1=RemoveArticles(n1).lower().strip()
    n2=RemoveArticles(n2).lower().strip()

    # We'd like them to match to the length of the shorter name
    length=min(len(n1), len(n2))
    return n1[:length] != n2[:length]

WriteTable(os.path.join(outputDir, "Reports", "Fanzines with odd names.txt"),
           fanacIssueList,
           lambda fz: fz.FanzineName,
           lambda fz: fz.FanzineIssueName,
           None,
           isDate=False,
           fSelector=lambda fx: OddNames(fx.FanzineIssueName,  fx.FanzineName))

print("\n")
print("All fanzines: Issues: "+str(issueCount)+"  Pages: "+str(pageCount)+"  PDFs: "+str(pdfCount))
print("Newszines: Issues: "+str(newsIssueCount)+"  Pages: "+str(newsPageCount)+"  PDFs: "+str(newsPdfCount))
print(str(selectedYear)+" Fanzines: "+str(countSelectedYear))
with open(os.path.join(outputDir, "Reports", "Statistics.txt"), "w+") as f:
    print("All fanzines: Issues: "+str(issueCount)+"  Pages: "+str(pageCount)+"  PDFs: "+str(pdfCount), file=f)
    print("Newszines: Issues: "+str(newsIssueCount)+"  Pages: "+str(newsPageCount)+"  PDFs: "+str(newsPdfCount), file=f)
    print(str(selectedYear)+" Fanzines: "+str(countSelectedYear), file=f)

Helpers.LogClose()

# Display a message box (needed only for the built/packaged version)
if sys.gettrace() is None:      # This is an incantation which detects the presence of a debugger
    root = Tk()
    root.withdraw()
    messagebox.showinfo(title=None, message="Finished!")

