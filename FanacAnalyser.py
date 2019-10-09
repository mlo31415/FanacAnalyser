from typing import TextIO

import Helpers
import FanacOrgReaders
import requests
from bs4 import BeautifulSoup
import os
import FanacDates
from tkinter import sys
#from tkinter import messagebox

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
    Helpers.LogFailureAndRaiseIfMissing("control-topleveldirectories.txt")
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


def ReadFile(filename):
    try:
        with open(filename, "r") as f2:
            return f2.readlines()

    except:
        # If the expected control header is unavailable, use the default.
        Helpers.LogFailureAndRaiseIfMissing(filename)
    return None

#================================================================================
# fRowHeaderText and fRowBodyText and fSelector are all lambdas
#   fSelector decides if this fanzines is to be listed and returns True for fanzines to be listed, and False for ones to be skipped. (If None, nothing will be skipped)
#   fRowHeaderText and fRowBodyText are functions which pull information out of a fanzineIssue from fanzineIssueList
#   fRowHeaderText is the item used to decide when to start a new subsection
#   fRowBodyText is what is listed in the subsection
def WriteTable(filename: str, fanacIssueList, fRowHeaderText, fRowBodyText, countText: str, headerFilename: str, isDate=True, fSelector=None):
    f: TextIO=open(filename, "w+")

    # Filename can end in ".html" or ".txt" and we output html or plain text accordingly
    html=os.path.splitext(filename)[1].lower() == ".html"
    if html:
        # When we're generating HTML output, we need to include a header.
        # It will be a combination of the contents of "control-Header (basic).html" with headerInfoFilename
        headerText=ReadFile("control-Header (basic).html")
        if headerText is None:
            return

        specialText=ReadFile(headerFilename)
        if specialText is not None:
            specialText=[s for s in specialText if len(s) > 0 and s[0] !="#"]   # Ignore comments
            title=specialText[0]
            del specialText[0]

            # Do the substitutions
            for i in range(0, len(headerText)):
                if headerText[i].strip() == "<title>title</title>":
                    headerText[i]="<title>" + title + "</title>"
                if headerText[i].strip() == "<h1>title</h1>":
                    headerText[i]="<h1>" + title + "</h1>"
            headerText.extend(specialText)

        f.writelines(headerText)

    if countText is not None:
        if html:
            countText="<p>"+countText+"<p>\n"
        f.write(countText)


    # If we have an HTML header, we need to create a set of jump buttons.
    # If it's alpha, the buttons are by 1st letter; if date it's by decade
    # First, we determine the potential button names.  There are two choices: Letters of the alphabet or decades
    if html:
        headers=set()
        for fz in fanacIssueList:
            if fSelector is not None and not fSelector(fz):
                continue
            if fRowHeaderText is not None:
                if isDate:
                    date=fRowHeaderText(fz)
                    if all(d in "0123456789" for d in date[-4:-1]):     # Only add all-numeric dates
                        headers.add(fRowHeaderText(fz)[-4:-1]+"0s")
                else:
                    headers.add(fRowHeaderText(fz)[:1])

        headerlist=list(headers)
        headerlist.sort()
        buttonlist=""
        for item in headerlist:
            if len(buttonlist) > 0:
                buttonlist=buttonlist+" &mdash; "
            buttonlist=buttonlist+'<a href="#' + item + '">' + item + '</a>\n'

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
            f.write('        <td width="350">'+'<a href="'+url+'">'+fz.FanzineIssueName.encode('ascii', 'xmlcharrefreplace').decode()+'</a>'+'</td>\n')
        else:
            f.write("   "+fRowBodyText(fz)+"\n")

        # And end the row
        if html: f.write('  </tr>\n')

    # And end everything
    if html:
        f.write("</table></td></tr>\n")
        f.write('</table>\n')
        try:
            Helpers.LogFailureAndRaiseIfMissing("control-Default.Footer")
            with open("control-Default.Footer", "r") as f2:
                f.writelines(f2.readlines())
        except:
            pass  # Except nothing, really.  If the file's not there, we ignore the whole thing.
    f.close()


# -------------------------------------------------------------------------
# We have a name and a dirname from the fanac.org Classic and Modern pages.
# The dirname *might* be a URL in which case it needs to be handled as a foreign directory reference
def AddFanacDirectory(fanacFanzineDirectories, name: str, dirname: str):

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

# Create a Reports directory if needed.
reportDir=os.path.join(outputDir, "Reports")
if not os.path.isdir(reportDir):
    try:
        os.mkdir(reportDir)
    except Exception as e:
        Helpers.Log("Fatal Error: Attempt to create directory "+reportDir+" yields exception: "+str(e), isError=True)
        exit(1)

# Read the fanac.org fanzine directory and produce a list of all issues and all newszines present
fanacFanzineDirectories=ReadClassicModernPages()
(fanacIssueList, newszinesFromH2)=FanacOrgReaders.ReadFanacFanzineIssues(fanacFanzineDirectories)

# Print a list of all fanzines sorted by fanzine name, then date
fanacIssueList.sort(key=lambda elem: elem.Date)
fanacIssueList.sort(key=lambda elem: elem.FanzineIssueName.lower())  # Sorts in place on fanzine name

def NoNone(s: str):
    if s is None:
        return ""
    return s


# Read the control-year.txt file to get the year to be dumped out
selectedYears=[]
if os.path.exists("control-year.txt"):
    years=Helpers.ReadList("control-year.txt")
    for year in years:
        file=open(os.path.join(reportDir, year+" fanac.org Fanzines.txt"), "w+")
        year=Helpers.InterpretNumber(year)
        yearCount=0
        for fz in fanacIssueList:
            if fz.Date.YearInt == year:
                file.write("|| "+NoNone(fz.FanzineIssueName)+" || "+NoNone(fz.Date.FormatDate())+" || " + NoNone(fz.DirectoryURL) +" || " + NoNone(fz.URL) + " ||\n")
                yearCount+=1
        file.close()
        selectedYears.append((year, yearCount)) # Create a list of tuples (selected year, count)


# Get a count of issues, pdfs, and pages
pageCount=0
issueCount=0
pdfCount=0
f=open(os.path.join(reportDir, "Items with No Page Count.txt"), "w+")
ignorePageCountErrors=Helpers.ReadList("control-Ignore Page Count Errors.txt")

for fz in fanacIssueList:
    if fz.URL is not None:
        issueCount+=1
        pageCount+=(fz.Pages if fz.Pages > 0 else 1)
        if os.path.splitext(fz.URL)[1] == ".pdf":
            pdfCount+=1
        if fz.Pages == 0 and ignorePageCountErrors is not None and fz.FanzineName not in ignorePageCountErrors:
            f.write(fz.FanzineName+"  "+fz.Serial.FormatSerial()+"\n")
f.close()

# Produce a list of fanzines listed by date
fanacIssueList.sort(key=lambda elem: elem.FanzineIssueName.lower(), reverse=True)  # Sorts in place on fanzine's name
fanacIssueList.sort(key=lambda elem: elem.Date)
undatedList=[f for f in fanacIssueList if f.Date.IsEmpty()]
datedList=[f for f in fanacIssueList if not f.Date.IsEmpty()]

countText=str(issueCount)+" issues consisting of "+str(pageCount)+" pages."
WriteTable(os.path.join(outputDir, "Chronological_Listing_of_Fanzines.html"),
           datedList,
           lambda fz: FanacDates.FormatDate2(fz.Date.YearInt, fz.Date.MonthInt, None),
           lambda fz: fz.FanzineIssueName,
           countText,
           'control-Header (Fanzine, chronological).html')
WriteTable(os.path.join(outputDir, "Chronological Listing of Fanzines.txt"),
           datedList,
           lambda fz: FanacDates.FormatDate2(fz.Date.YearInt, fz.Date.MonthInt, None),
           lambda fz: fz.FanzineIssueName,
           countText,
           None)
WriteTable(os.path.join(reportDir, "Undated Fanzine Issues.html"),
           undatedList,
           None,
           lambda fz: fz.FanzineIssueName,
           "",
           "control-Header (Fanzine, alphabetical).html")

# Get the names of the newszines as a list
Helpers.LogFailureAndRaiseIfMissing("control-newszines.txt")
listOfNewszines=Helpers.ReadList("control-newszines.txt", isFatal=True)
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
    if fz.FanzineName in listOfNewszines and fz.URL is not None:
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
with open(os.path.join(reportDir, "Items identified as newszines.txt"), "w+") as f:
    f.writelines(newszines)
with open(os.path.join(reportDir, "Unused lines in control-newszines.txt"), "w+") as f:
    f.writelines(unusedLines)
nonNewszines=[x+"\n" for x in nonNewszines]
with open(os.path.join(reportDir, "Items identified as non-newszines.txt"), "w+") as f:
    f.writelines(nonNewszines)

newszinesFromH2=[x+"\n" for x in newszinesFromH2]
with open(os.path.join(reportDir, "Items identified as newszines by H2 tags.txt"), "w+") as f:
    f.writelines(newszinesFromH2)

countText=str(newsIssueCount)+" issues consisting of "+str(newsPageCount)+" pages."
WriteTable(os.path.join(outputDir, "Chronological_Listing_of_Newszines.html"),
           fanacIssueList,
           lambda fz: FanacDates.FormatDate2(fz.Date.YearInt, fz.Date.MonthInt, None),
           lambda fz: fz.FanzineIssueName,
           countText,
           "control-Header (Newszine).html",
           fSelector=lambda fx: fx.FanzineName.lower() in listOfNewszines)

# Produce a list of fanzines by title
countText=str(issueCount)+" issues consisting of "+str(pageCount)+" pages."
fanacIssueList.sort(key=lambda elem: elem.Date)  # Sorts in place on Date
fanacIssueList.sort(key=lambda elem: elem.FanzineName.lower())  # Sorts in place on fanzine's name
WriteTable(os.path.join(outputDir, "Alphabetical Listing of Fanzines.txt"),
           fanacIssueList,
           lambda fz: fz.FanzineName,
           lambda fz: fz.FanzineIssueName,
           countText,
           None,
           isDate=False)
WriteTable(os.path.join(outputDir, "Alphabetical_Listing_of_Fanzines.html"),
           fanacIssueList,
           lambda fz: fz.FanzineName,
           lambda fz: fz.FanzineIssueName,
           countText,
           "control-Header (Fanzine, alphabetical).html",
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
# This function is used only in the lambda expression following immediately afterwards.
def OddNames(n1, n2):
    n1=RemoveArticles(n1).lower().strip()
    n2=RemoveArticles(n2).lower().strip()

    # We'd like them to match to the length of the shorter name
    length=min(len(n1), len(n2))
    return n1[:length] != n2[:length]

WriteTable(os.path.join(reportDir, "Fanzines with odd names.txt"),
           fanacIssueList,
           lambda fz: fz.FanzineName,
           lambda fz: fz.FanzineIssueName,
           None,
           None,
           isDate=False,
           fSelector=lambda fx: OddNames(fx.FanzineIssueName,  fx.FanzineName))

# Count the number of distinct fanzine names (not issue names, but names of runs of fanzines.)
# Create a set of all fanzines run names (the set to eliminate suploicates) and then get its size.
fzCount=len(set([fz.FanzineName.lower() for fz in fanacIssueList]))
nzCount=len(set([fz.FanzineName.lower() for fz in fanacIssueList if fz.FanzineName.lower() in listOfNewszines]))

# Print to the console and also the statistics file
print("\n")
print("All fanzines: Titles: "+str(fzCount)+"  Issues: "+str(issueCount)+"  Pages: "+str(pageCount)+"  PDFs: "+str(pdfCount))
print("Newszines:  Titles: "+str(nzCount)+"  Issues: "+str(newsIssueCount)+"  Pages: "+str(newsPageCount)+"  PDFs: "+str(newsPdfCount))
for selectedYear in selectedYears:
    print(str(selectedYear[0])+" Fanzines: "+str(selectedYear[1]))
with open(os.path.join(outputDir, "Statistics.txt"), "w+") as f:
    print("All fanzines: Titles: "+str(fzCount)+"  Issues: "+str(issueCount)+"  Pages: "+str(pageCount)+"  PDFs: "+str(pdfCount), file=f)
    print("Newszines:  Titles: "+str(nzCount)+"  Issues: "+str(newsIssueCount)+"  Pages: "+str(newsPageCount)+"  PDFs: "+str(newsPdfCount), file=f)
    for selectedYear in selectedYears:
        print(str(selectedYear[0])+" Fanzines: "+str(selectedYear[1]), file=f)

# Generate a list of fanzines with odd page counts
def OddPageCount(fz: FanacOrgReaders.FanacIssueInfo):
    if fz.Pages > 250:
        return True
    return False

WriteTable(os.path.join(reportDir, "Fanzines with odd page counts.txt"),
           fanacIssueList,
           lambda fz: fz.FanzineName,
           lambda fz: fz.FanzineIssueName,
           None,
           None,
           isDate=False,
           fSelector=lambda fx: OddPageCount(fx))

Helpers.LogClose()

# Display a message box (needed only for the built/packaged version)
# if sys.gettrace() is None:      # This is an incantation which detects the presence of a debugger
#    root = Tk()
#    root.withdraw()
#    messagebox.showinfo(title=None, message="Finished!")

