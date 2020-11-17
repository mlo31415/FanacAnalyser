from typing import TextIO, List, Tuple, Optional, Callable, Any
from time import localtime, strftime
import requests
import os
import sys
from bs4 import BeautifulSoup
import unidecode

import FanacOrgReaders
from FanzineIssueSpecPackage import FanzineIssueInfo, FanzineSeriesInfo, FanzineCounts
from Log import Log, LogOpen, LogClose, LogFlush, LogFailureAndRaiseIfMissing
from HelpersPackage import ReadList, FormatLink, InterpretNumber, UnicodeToHtml, RemoveArticles

LogOpen("Log - Fanac Analyzer Detailed Analysis Log.txt", "Log - Fanac Analyzer Error Log.txt")

# ====================================================================================
# Read fanac.org/fanzines/Classic_Fanzines.html amd /Modern_Fanzines.html
# Read the table to get a list of all the fanzines on Fanac.org
# Return a list of tuples (name on page, name of directory)
#       The name on page is the display named used in the Classic and Modern tables
#       The name of directory is the name of the directory pointed to

def ReadAllFanacFanzineMainPages() -> List[Tuple[str, str]]:
    Log("----Begin reading Classic and Modern tables")
    # This is a list of fanzines on Fanac.org
    # Each item is a tuple of (compressed name,  link name,  link url)
    fanacFanzineDirectoriesList=[]
    LogFailureAndRaiseIfMissing("control-topleveldirectories.txt")
    directories=ReadList("control-topleveldirectories.txt")
    for dirs in directories:
        ReadModernOrClassicTable(fanacFanzineDirectoriesList, dirs)

    Log("----Done reading Classic and Modern tables")
    return fanacFanzineDirectoriesList


# ======================================================================
# Read one of the main fanzine directory listings and append all the fanzines directories found to the dictionary
def ReadModernOrClassicTable(fanacFanzineDirectoriesList: List[Tuple[str, str]], url: str) -> None:
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
                try:
                    if len(trs[i].find_all("td")[1].contents[0].contents[0]) > 0:   # I've seen bogus entries where this isn't true
                        name=trs[i].find_all("td")[1].contents[0].contents[0].contents[0]
                        dirname=trs[i].find_all("td")[1].contents[0].attrs["href"][:-1]
                        AddFanacDirectory(fanacFanzineDirectoriesList, name, dirname)
                except:
                    Log("Bogus row found by ReadModernOrClassicTable", isError=True)    # There's really nothing to be done except debug...
                    assert()    #TODO: Remove this, as it is temporary
    return


def ReadFile(filename: str) -> Optional[List[str]]:
    try:
        with open(filename, "r") as f2:
            return f2.readlines()

    except:
        # If the expected control header is unavailable, use the default.
        LogFailureAndRaiseIfMissing(filename)
    return None

#================================================================================
# fRowHeaderText and fRowBodyText and fSelector are all lambdas
#   fSelector decides if this fanzines is to be listed and returns True for fanzines to be listed, and False for ones to be skipped. (If None, nothing will be skipped)
#   fButtonText operates on an issue and selects the character (or whatever) that will be used for button grouping
#   fRowHeaderText and fRowBodyText are functions which pull information out of a fanzineIssue from fanzineIssueList
#   fRowHeaderText is the item used to decide when to start a new subsection
#   fRowBodyText is what is listed in the subsection
def WriteTable(filename: str,
               fanacIssueList: List,        # The sorted input list
               fRowBodyText: Callable[[Any], str],         # Function to supply the row's body text
               fButtonText: Optional[Callable[[Any], str]]=None,    # Function to supply the button text
               fRowHeaderText: Optional[Callable[[Any], str]]=None,     # Function to supply the header text
               fURL: Optional[Callable[[Any], str]]=None,         # Function to supply the URL
               fDirURL: Optional[Callable[[Any], str]]=None,         # Function to supply the directory or root URL
               fAnnot: Optional[Callable[[Any], str]]=None,         # Function to supply annotation
               countText: Optional[str]=None,
               headerFilename: Optional[str]=None,
               fSelector: Optional[Callable[[Any], bool]]=None,
               isAlpha: bool=False)\
                -> None:
    f: TextIO=open(filename, "w+")

    #....... Header .......
    # Filename can end in ".html" or ".txt" and we output html or plain text accordingly
    html=os.path.splitext(filename)[1].lower() == ".html"
    if html:
        # When we're generating HTML output, we need to include a header.
        # It will be a combination of the contents of "control-Header (basic).html" with headerInfoFilename
        basicHeadertext=ReadFile("control-Header (basic).html")
        if basicHeadertext is None:
            return

        # Read the specialized control.html file for this type of report
        specialText=ReadFile(headerFilename)
        if specialText is not None:
            specialText=[s for s in specialText if len(s) > 0 and s[0] !="#"]   # Ignore comments
            title=specialText[0]
            del specialText[0]

            # Do the substitutions
            for i in range(0, len(basicHeadertext)):
                if basicHeadertext[i].strip() == "<title>title</title>":
                    basicHeadertext[i]="<title>" + title + "</title>"
                if basicHeadertext[i].strip() == "<h1>title</h1>":
                    basicHeadertext[i]="<h1>" + title + "</h1>"
            basicHeadertext.extend(specialText)

        f.writelines(basicHeadertext)

    if countText is not None:
        if html:
            countText=countText.replace("\n", "<p>")
            countText="<p>"+countText+"</p>\n"
        f.write(countText)


    #....... Jump buttons .......
    # If we have an HTML header, we need to create a set of jump buttons.
    # If it's alpha, the buttons are by 1st letter; if date it's by decade
    # First, we determine the potential button names.  There are two choices: Letters of the alphabet or decades
    if html:
        headers=set()
        for fz in fanacIssueList:
            if fSelector is not None and not fSelector(fz):
                continue
            if fButtonText is not None:
                if fButtonText(fz) is not None:
                    headers.add(fButtonText(fz))

        headerlist=list(headers)
        headerlist.sort()
        buttonlist=""
        for item in headerlist:
            if len(buttonlist) > 0:
                buttonlist=buttonlist+" &mdash; "
            buttonlist+=FormatLink("#"+ item, item)

        # Write out the button bar
        f.write(buttonlist+"<p><p>\n")

    #....... Main table .......
    # Start the table if this is HTML
    # The structure is
    #   <div class="row border">        # This starts a new bordered box (a fanzine, a month)
    #       <div class=col_md_2> (1st col: box title) </div>
    #       <div class=col_md_10> (1nd col, a list of fanzine issues)
    #           <a>issue</a> <br>
    #           <a>issue</a> <br>
    #           <a>issue</a> <br>
    #       </div>
    #   </div>
    if html:
        f.write('<div>\n')  # Begin the main table

    lastRowHeader=None
    lastButtonLinkString=None
    for fz in fanacIssueList:
        # Do we skip this fanzine
        if fSelector is not None and not fSelector(fz):
            continue
        if html and fURL is not None and fURL(fz) is None:
            continue

        # Get the button link string, to see if we have a new decade (or 1st letter) and need to create a new jump anchor
        buttonLinkString=""
        if html:
            if fButtonText is not None:
                if fButtonText(fz) is not None:
                    buttonLinkString=fButtonText(fz)

        # Start a new row
        # Deal with Column 1
        if fRowHeaderText is not None and lastRowHeader != fRowHeaderText(fz):
            if lastRowHeader is not None:  # If this is not the first sub-box, we must end the previous sub-box by ending its col 2
                if html: f.write('    </div></div>\n')
            lastRowHeader=fRowHeaderText(fz)

            # Since this is a new sub-box, we write the header in col 1
            if html:
                if buttonLinkString != lastButtonLinkString:
                    f.write('<a name="'+UnicodeToHtml(buttonLinkString)+'"></a>')
                    lastButtonLinkString=buttonLinkString
                f.write('<div class="row border">\n')  # Start a new sub-box
                # Write col 1
                f.write('  <div class=col-md-3>')
                if isAlpha:
                    if fDirURL is not None:
                        f.write(FormatLink(fDirURL(fz), lastRowHeader))
                    else:
                        f.write(lastRowHeader)
                else:
                    f.write(UnicodeToHtml(lastRowHeader))
                f.write('</div>\n')
                f.write('    <div class=col-md-9>\n') # Start col 2
            else:
                f.write("\n"+lastRowHeader+"\n")

        # Deal with Column 2
        # The hyperlink goes in column 2
        # There are two kinds of hyperlink: Those with just a filename (xyz.html) and those with a full URL (http://xxx.vvv.zzz.html)
        # The former are easy, but the latter need to be processed
        if html:
            if fURL is not None:
                f.write('        '+FormatLink(fURL(fz), fRowBodyText(fz)))
            else:
                f.write('        '+fRowBodyText(fz))
            if isAlpha:
                f.write("&nbsp;&nbsp;&nbsp;&nbsp;"+("" if fAnnot is None or fAnnot(fz) is None else fAnnot(fz)))
            f.write('<br>\n')
        else:
            f.write("   "+fRowBodyText(fz)+"\n")

    #....... Cleanup .......
    # And end everything
    if html:
        f.write('</div>\n</div>\n')
        try:
            LogFailureAndRaiseIfMissing("control-Default.Footer")
            with open("control-Default.Footer", "r") as f2:
                f.writelines(f2.readlines())
        except e:
            Log("Exception "+str(e)+" raised while opening control-Default.Footer", isError=True)
    f.close()


# -------------------------------------------------------------------------
# We have a name and a dirname from the fanac.org Classic and Modern pages.
# The dirname *might* be a URL in which case it needs to be handled as a foreign directory reference
def AddFanacDirectory(fanacFanzineDirectoriesList: List[Tuple[str, str]], name: str, dirname: str) -> None:

    # We don't want to add duplicates. A duplicate is one which has the same dirname, even if the text pointing to it is different.
    dups=[e2 for e1, e2 in fanacFanzineDirectoriesList if e2 == dirname]
    if len(dups) > 0:
        Log("   duplicate: name="+name+"  dirname="+dirname)
        return

    if dirname[:3]=="http":
        Log("    ignored, because is HTML: "+dirname)
        return

    # Add name and directory reference
    Log("   added to fanacFanzineDirectories:  name='"+name+"'  dirname='"+dirname+"'")
    fanacFanzineDirectoriesList.append((name, dirname))
    return


#===========================================================================
#===========================================================================
# Main
Log("Started")
LogFlush()

# Read the command line arguments
outputDir="."
if len(sys.argv) > 1:
    outputDir=sys.argv[1]
if not os.path.isdir(outputDir):
    os.mkdir(outputDir)

Log("Output directory '"+outputDir+"' set")
LogFlush()

# Create a Reports directory if needed.
reportDir=os.path.join(outputDir, "Reports")
if not os.path.isdir(reportDir):
    try:
        os.mkdir(reportDir)
    except Exception as e:
        Log("***Fatal Error: Attempt to create directory "+reportDir+" yields exception: "+str(e), isError=True)
        exit(1)
Log("Report directory '"+reportDir+"' created")
LogFlush()

# Read the fanac.org fanzine index page structures and produce a list of all fanzines series directories
fanacFanzineDirectories=ReadAllFanacFanzineMainPages()

# Read the directories list and produce a list of all fanzine issues
fanacIssueList=FanacOrgReaders.ReadFanacFanzineIssues(fanacFanzineDirectories)

# Sort the list of all fanzines issues by fanzine series name
fanacIssueList.sort(key=lambda elem: elem.SeriesName.lower())  # Sorts in place on fanzine name

def NoNone(s: str) -> str:
    if s is None:
        return ""
    return s


# Read the control-year.txt file to get the year to be dumped out
selectedYears=[]
if os.path.exists("control-year.txt"):
    years=ReadList("control-year.txt")
    for year in years:      # For each year in the list of years to be dumped
        file=open(os.path.join(reportDir, year+" fanac.org Fanzines.txt"), "w+")
        year=InterpretNumber(year)
        yearCount=0
        for fz in fanacIssueList:
            if fz.FIS.Year == year:
                file.write("|| "+NoNone(fz.IssueName)+" || "+NoNone(str(fz.FIS))+" || " + NoNone(fz.DirURL) +" || " + NoNone(fz.PageName) + " ||\n")
                yearCount+=1
        file.close()
        selectedYears.append((year, yearCount)) # Create a list of tuples (selected year, count)


# Count the number of pages, issues and PDFs and also generate a report listing all fanzines for which a page count can't be locatedpageCount=0
issueCount=0
pdfCount=0
pageCount=0
f=open(os.path.join(reportDir, "Items with No Page Count.txt"), "w+")
ignorePageCountErrors=ReadList("control-Ignore Page Count Errors.txt")

for fz in fanacIssueList:
    if fz.DirURL is not None:
        issueCount+=1
        pageCount+=(fz.Pagecount if fz.Pagecount > 0 else 1)
        if os.path.splitext(fz.DirURL)[1] == ".pdf":
            pdfCount+=1
        if fz.Pagecount == 0 and ignorePageCountErrors is not None and fz.SeriesName not in ignorePageCountErrors:
            f.write(str(fz)+"\n")
f.close()

# Produce a list of fanzines listed by date
fanacIssueList.sort(key=lambda elem: elem.IssueName.lower())  # Sorts in place on fanzine's name
fanacIssueList.sort(key=lambda elem: elem.FIS.FormatDateForSorting())
undatedList=[f for f in fanacIssueList if f.FIS.IsEmpty()]
datedList=[f for f in fanacIssueList if not f.FIS.IsEmpty()]

timestamp="Indexed as of "+strftime("%Y-%m-%d %H:%M:%S", localtime())+" EST"

def ChronButtonText(fz: FanzineIssueInfo) -> str:
    if fz.FIS is None or fz.FIS.Year is None:
        return " "
    return str(fz.FIS.Year)[0:3]+"0s"

def URL(fz: FanzineIssueInfo) -> str:
    if fz is None or fz.PageName is None:
        return "<no url>"
    if "/" not in fz.PageName:
        url=fz.DirURL+"/"+fz.PageName
    else:
        # There are two possibilities: This is a reference to somewhere in the fanzines directory or this is a reference elsewhere.
        # If it is in fanzines, then the url ends with <stuff>/fanzines/<dir>/<file>.html
        parts=fz.PageName.split("/")
        if len(parts) > 2 and parts[-3:-2][0] == "fanzines":
            url=fz.DirURL+"/../"+"/".join(parts[-2:])
        else:
            url=fz.PageName
    return url

countText="{:,}".format(issueCount)+" issues consisting of "+"{:,}".format(pageCount)+" pages."
WriteTable(os.path.join(outputDir, "Chronological_Listing_of_Fanzines.html"),
           datedList,
           lambda fz: fz.IssueName,
           fButtonText=lambda fz: ChronButtonText(fz),
           fRowHeaderText=lambda fz: (fz.FIS.MonthText+" "+fz.FIS.YearText).strip(),
           fURL=URL,
           countText=countText+"\n"+timestamp+"\n",
           headerFilename='control-Header (Fanzine, chronological).html')
WriteTable(os.path.join(outputDir, "Chronological Listing of Fanzines.txt"),
           datedList,
           lambda fz: fz.IssueName,
           fButtonText=lambda fz: ChronButtonText(fz),
           fRowHeaderText=lambda fz: (fz.FIS.MonthText+" "+fz.FIS.YearText).strip(),
           countText=countText+"\n"+timestamp+"\n")
WriteTable(os.path.join(reportDir, "Undated Fanzine Issues.html"),
           undatedList,
           lambda fz: fz.IssueName,
           fURL=URL,
           countText=timestamp,
           headerFilename="control-Header (Fanzine, alphabetical).html")

# Generate a list of all the newszines (in lower case)
# This takes names from the file control-newszines.txt and adds fanzines tagged as newszines on their series index page

# Read the control-newszines.txt file
LogFailureAndRaiseIfMissing("control-newszines.txt")
newszinesSet=set([x.lower() for x in ReadList("control-newszines.txt", isFatal=True)])

# Add in the newszines discovered in the <h2> blocks
newszinesFromH2Set=set([fii.SeriesName.lower() for fii in fanacIssueList if "newszine" in fii.Taglist])
with open(os.path.join(reportDir, "Items identified as newszines by H2 tags.txt"), "w+") as f:
    newszinesFromH2List=sorted(list(newszinesFromH2Set))
    for nz in newszinesFromH2List:
        f.write(nz+"\n")

newszinesSet=newszinesSet.union(newszinesFromH2Set)

# Make up a lists of newszines and non-newszines
allzinesSet=set([fx.SeriesName.lower() for fx in fanacIssueList])

with open(os.path.join(reportDir, "Items identified as non-newszines.txt"), "w+") as f:
    nonNewszines=sorted(list(allzinesSet.difference(newszinesSet)))
    for nnz in nonNewszines:
        f.write(nnz+"\n")

listOfNewszines=sorted(list(newszinesSet))

# Count the number of issue and pages of all fanzines and just newszines
newsPageCount=0
newsIssueCount=0
newsPdfCount=0
for fz in fanacIssueList:
    if fz.SeriesName in listOfNewszines and fz.PageName is not None:
        newsIssueCount+=1
        if os.path.splitext(fz.PageName)[1].lower() == ".pdf":
            newsPdfCount+=1
            newsPageCount+=1
        else:
            newsPageCount+=(fz.Pagecount if fz.Pagecount > 0 else 1)

# Look for lines in the list of newszines which don't match actual newszines on the site.
unusedLines=[x for x in listOfNewszines if x.lower() not in listOfNewszines]
unusedLines=[x+"\n" for x in unusedLines]

newszines=[x+"\n" for x in listOfNewszines]
with open(os.path.join(reportDir, "Items identified as newszines.txt"), "w+") as f:
    f.writelines(newszines)
with open(os.path.join(reportDir, "Unused lines in control-newszines.txt"), "w+") as f:
    f.writelines(unusedLines)

countText="{:,}".format(newsIssueCount)+" issues consisting of "+"{:,}".format(newsPageCount)+" pages."
WriteTable(os.path.join(outputDir, "Chronological_Listing_of_Newszines.html"),
           fanacIssueList,
           lambda fz: fz.IssueName,
           fButtonText=lambda fz: ChronButtonText(fz),
           fRowHeaderText=lambda fz: (fz.FIS.MonthText+" "+fz.FIS.YearText).strip(),
           fURL=URL,
           countText=countText+"\n"+timestamp+"\n",
           headerFilename="control-Header (Newszine).html",
           fSelector=lambda fz: fz.SeriesName.lower() in listOfNewszines)

# Produce a list of fanzines by title
def AlphaSortText(fz: FanzineIssueInfo) -> str:
    if fz.SeriesName is None or len(fz.SeriesName) == 0:
        return " "
    # Replace lower case and accented alphas, ignore punctuation, retain digits; the Unidecode is so that things like 'á Bas' sort with A
    out=""
    for c in fz.SeriesName:
        if c.isalpha():
            out+=unidecode.unidecode(c.upper())
        elif c.isdigit():
            out+=c
    return out
countText="{:,}".format(issueCount)+" issues consisting of "+"{:,}".format(pageCount)+" pages."
fanacIssueList.sort(key=lambda elem: elem.FIS.FormatDateForSorting())  # Sorts in place on order in index page, which is usually a good proxy for date
fanacIssueList.sort(key=lambda elem: AlphaSortText(elem))  # Sorts in place on fanzine's name


def AlphaButtonText(fz: FanzineIssueInfo) -> str:
    c=AlphaSortText(fz)[0]
    if c == " " or c.isdigit():
        return "*"
    return c

def Annotate(fz: FanzineIssueInfo) -> str:
    if type(fz) is not FanzineIssueInfo:
        assert()
    if fz.FIS is None:
        return ""
    if fz.FIS.FD.IsEmpty():
        return ""
    return "<small>("+str(fz.FIS.FD.LongDates)+')</small>'

WriteTable(os.path.join(outputDir, "Alphabetical Listing of Fanzines.txt"),
           fanacIssueList,
           lambda fz: fz.IssueName,
           fButtonText=lambda fz: fz.SeriesName[0],
           fRowHeaderText=lambda fz: fz.SeriesName,
           countText=countText+"\n"+timestamp+"\n",
           isAlpha=True)
WriteTable(os.path.join(outputDir, "Alphabetical_Listing_of_Fanzines.html"),
           fanacIssueList,
           lambda fz: fz.IssueName,
           fButtonText=lambda fz: AlphaButtonText(fz),
           fAnnot=lambda fz: Annotate(fz),
           fRowHeaderText=lambda fz: fz.SeriesName,
           fURL=URL,
           countText=countText+"\n"+timestamp+"\n",
           headerFilename="control-Header (Fanzine, alphabetical).html",
           isAlpha=True)


# Read through the alphabetic list and generate a flag file of cases where the issue name doesn't match the serial name
# This function is used only in the lambda expression following immediately afterwards.
def OddNames(n1: str, n2: str) -> bool:
    n1=RemoveArticles(n1).lower().strip()
    n2=RemoveArticles(n2).lower().strip()
    # We'd like them to match to the length of the shorter name
    length=min(len(n1), len(n2))
    return n1[:length] != n2[:length]

WriteTable(os.path.join(reportDir, "Fanzines with odd names.txt"),
           fanacIssueList,
           lambda fz: fz.IssueName,
           fButtonText=lambda fz: fz.SeriesName[0],
           fRowHeaderText=lambda fz: fz.SeriesName,
           countText=timestamp+"\n",
           fSelector=lambda fx: OddNames(fx.IssueName,  fx.SeriesName))

# Count the number of distinct fanzine names (not issue names, but names of runs of fanzines.)
# Create a set of all fanzines run names (the set to eliminate suploicates) and then get its size.
fzCount=len(set([fz.SeriesName.lower() for fz in fanacIssueList]))
nzCount=len(set([fz.SeriesName.lower() for fz in fanacIssueList if fz.SeriesName.lower() in listOfNewszines]))

# Print to the console and also the statistics file
Log("\n")
Log("All fanzines: Titles: "+"{:,}".format(fzCount)+"  Issues: "+"{:,}".format(issueCount)+"  Pages: "+"{:,}".format(pageCount)+"  PDFs: "+"{:,}".format(pdfCount))
Log("Newszines:  Titles: "+"{:,}".format(nzCount)+"  Issues: "+"{:,}".format(newsIssueCount)+"  Pages: "+"{:,}".format(newsPageCount)+"  PDFs: "+"{:,}".format(newsPdfCount))
for selectedYear in selectedYears:
    Log(str(selectedYear[0])+" Fanzines: "+str(selectedYear[1]))
with open(os.path.join(outputDir, "Statistics.txt"), "w+") as f:
    print("All fanzines: Titles: "+"{:,}".format(fzCount)+"  Issues: "+"{:,}".format(issueCount)+"  Pages: "+"{:,}".format(pageCount)+"  PDFs: "+"{:,}".format(pdfCount), file=f)
    print("Newszines:  Titles: "+"{:,}".format(nzCount)+"  Issues: "+"{:,}".format(newsIssueCount)+"  Pages: "+"{:,}".format(newsPageCount)+"  PDFs: "+"{:,}".format(newsPdfCount), file=f)
    for selectedYear in selectedYears:
        print(str(selectedYear[0])+" Fanzines: "+str(selectedYear[1]), file=f)

WriteTable(os.path.join(reportDir, "Fanzines with odd page counts.txt"),
           fanacIssueList,
           lambda fz: fz.IssueName,
           fButtonText=lambda fz: fz.SeriesName[0],
           fRowHeaderText=lambda fz: fz.SeriesName,
           countText=timestamp,
           fSelector=lambda fz: fz.Pagecount > 250)

# Now generate a list of fanzine series sorted by country
# For this, we don't actually want a list of individual issues, so we need to collapse fanacIssueList into a fanzineSeriesList
# FanacIssueList is a list of FanzineIssueInfo objects.  We will read through them all and create a dictionary keyed by fanzine series name with the country as value.
fanacSeriesDictByCountry={}     # Key is country code; value is a tuple of (issuecount, pagecount, list of newly-constructed FSIs, one per fanzine series)
for issue in fanacIssueList:
    # If this is a new country, create a new, empty entry for it
    country=issue.Country.lower()
    if country not in fanacSeriesDictByCountry.keys():
        fanacSeriesDictByCountry[country]=([], FanzineCounts())     # Add an empty country entry

    serieslist=fanacSeriesDictByCountry[country][0]
    # serieslist is the list of fanzine series with counts for this country
    # Note that we accumulate the series page and issue totals

    # Create an FSI for this issue
    fsi=FanzineSeriesInfo(SeriesName=issue.SeriesName, DirURL=issue.DirURL, Issuecount=1, Pagecount=issue.Pagecount, Editor=issue.Editor, Country=issue.Country)
    if fsi.Pagecount == 0:
        continue

    # Is this new issue from a series that is already in the list for this country?
    found=False
    for i in range(len(serieslist)):
        if fsi == serieslist[i]:
            # Yes: If the directories in the DirURLs match, just add this issue to the existing series totals.
            # If they don't match, just skip it because it's probably one of the doubly-referred-to entries and will be picked up in some other series.
            if fsi.DirURL == serieslist[i].DirURL:
                # serieslist[loc] is a specific series in [country]
                # Update the series by adding the pagecount of this issue to it
                serieslist[i]+=fsi.Pagecount
                fanacSeriesDictByCountry[country]=(fanacSeriesDictByCountry[country][0], fanacSeriesDictByCountry[country][1]+fsi.Pagecount)
                found=True
            break
    # No: Add a new series entry from this issue
    if not found:
        serieslist.append(fsi)
        fanacSeriesDictByCountry[country]=(fanacSeriesDictByCountry[country][0], fanacSeriesDictByCountry[country][1]+fsi.Pagecount)

# Next we sort the individual country lists into order by series name
for ckey, cval in fanacSeriesDictByCountry.items():
    serieslist=cval[0]
    serieslist.sort(key=lambda elem: elem.SeriesName.lower())
    fanacSeriesDictByCountry[ckey]=(serieslist, cval[1])  # Sorts in place on fanzine name

def CapIt(s: str) -> str:
    if len(s) == 0:
        return s
    if len(s) == 2:
        return s.upper()
    return s[0].upper()+s[1:]

# List out the series by country data
with open(os.path.join(reportDir, "Series by Country.txt"), "w+") as f:
    keys=list(fanacSeriesDictByCountry.keys())
    keys.sort() # We want to list the countries in alphabetical order
    for key in keys:
        val=fanacSeriesDictByCountry[key]
        k=key if len(key.strip()) > 0 else "<no country>"
        print("\n"+CapIt(k)+"   "+str(len(val[0]))+" titles,  "+str(val[1].Issuecount)+" issues,  and "+str(val[1].Pagecount)+" pages", file=f)
        for series in val[0]:
            print("    "+series.SeriesName+"    ("+str(series.Issuecount)+" issues, "+str(series.Pagecount)+" pages)", file=f)
            Log("    "+series.SeriesName+"    ("+str(series.Issuecount)+" issues, "+str(series.Pagecount)+" pages)")

# Now create a properly ordered flat list suirtable for WriteTable
fanacFanzineSeriesListByCountry=[]
for country, countryEntries in fanacSeriesDictByCountry.items():
    for v in countryEntries[0]:
        fanacFanzineSeriesListByCountry.append((country, v))       # (country, series)
fanacFanzineSeriesListByCountry.sort(key=lambda elem: elem[1].SeriesName.lower())
fanacFanzineSeriesListByCountry.sort(key=lambda elem: elem[0].lower())

WriteTable(os.path.join(outputDir, "Series_by_Country.html"),
           fanacFanzineSeriesListByCountry,
           lambda elem: elem[1].SeriesName,
           fRowHeaderText=lambda elem: CapIt(elem[0]),
           fURL=lambda elem: elem[1].DirURL,
           countText="timestamp",  #countText+"\n"+timestamp+"\n",
           headerFilename="control-Header (Fanzine, by country).html",
           isAlpha=True)

LogClose()
