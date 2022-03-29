from typing import TextIO, Optional, Callable, Any, Set
from time import localtime, strftime
import requests
import os
import sys
import re
import math
import datetime
from bs4 import BeautifulSoup
import unidecode
from collections import namedtuple

import FanacOrgReaders
from FanzineIssueSpecPackage import FanzineIssueInfo, FanzineCounts, FanzineSeriesInfo
from Log import Log, LogOpen, LogClose, LogFailureAndRaiseIfMissing
from HelpersPackage import ReadList, FormatLink, InterpretNumber, UnicodeToHtml, RemoveArticles, RemoveAccents, RemoveAllHTMLTags2

def main():
    LogOpen("Log - Fanac Analyzer Detailed Analysis Log.txt", "Log - Fanac Analyzer Error Log.txt")
    Log("Started")

    # Read the command line arguments
    outputDir="."
    if len(sys.argv) > 1:
        outputDir=sys.argv[1]
    if not os.path.isdir(outputDir):
        os.mkdir(outputDir)

    Log("Output directory '"+outputDir+"' set")

    # Create a Reports directory if needed.
    reportDir=os.path.join(outputDir, "Reports")
    if not os.path.isdir(reportDir):
        try:
            os.mkdir(reportDir)
        except Exception as e:
            Log(f"***Fatal Error: Attempt to create directory {reportDir} yields exception: {e}", isError=True)
            exit(1)
    Log("Report directory '"+reportDir+"' created")

    # Read the fanac.org fanzine index page structures and produce a list of all fanzine series directories
    fanacFanzineDirectories=ReadAllFanacFanzineMainPages()

    # Read the directories list and produce a list of all fanzine issues
    fanacIssueList=FanacOrgReaders.ReadFanacFanzineIssues(fanacFanzineDirectories)

    # Remove issues which have entries, but don't actually point to anything.
    fanacIssueList=[x for x in fanacIssueList if x.PageName != ""]

    # Sort the list of all fanzines issues by fanzine series name
    fanacIssueList.sort(key=lambda elem: elem.SeriesName.lower())  # Sorts in place on fanzine name

    def NoNone(s: str) -> str:
        if s is None:
            return ""
        return s

    # Read the control-year.txt file to get the year(s) to be dumped out
    selectedYears: list[tuple[int, int]]=[]
    if os.path.exists("control-year.txt"):
        years=ReadList("control-year.txt")
        for year in years:  # For each year in the list of years to be dumped
            file=open(os.path.join(reportDir, f"{year} fanac.org Fanzines.txt"), "w+")
            year=InterpretNumber(year)
            yearCount=0
            for fz in fanacIssueList:
                if fz.FIS.Year == year:
                    file.write(f"|| {fz.IssueName} || {NoNone(str(fz.FIS))} || {fz.DirURL} || {fz.PageName} ||\n")
                    yearCount+=1
            file.close()
            selectedYears.append((year, yearCount))  # Create a list of tuples (selected year, count)

    # Count the number of pages, issues and PDFs
    ignorePageCountErrors=ReadList("control-Ignore Page Count Errors.txt")

    counts=FanzineCounts()
    for fz in fanacIssueList:
        if fz.DirURL != "":
            counts+=fz.Pagecount
            if os.path.splitext(fz.PageName)[1].lower() == ".pdf":
                counts.Pdfcount+=1
                counts.Pdfpagecount+=fz.Pagecount
            if fz.Pagecount == 0 and ignorePageCountErrors is not None and fz.SeriesName not in ignorePageCountErrors:
                Log(f"{fz.IssueName} has no page count: {fz}")

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
        if fz is None or fz.PageName == "":
            return "<no url>"
        # Sometimes the url will be to a page in a PDF, so the URL will end with #page=nnn
        # Detect that, since the page needs to be handled specially.
        page=""
        url=fz.DirURL
        m=re.match("(.*)(#page=[0-9]+)$", url)
        if m is not None:
            url=m.groups()[0]
            page=m.groups()[1]

        if "/" not in fz.PageName:
            url=url+"/"+fz.PageName+page
        else:
            # There are two possibilities: This is a reference to somewhere in the fanzines directory or this is a reference elsewhere.
            # If it is in fanzines, then the url ends with <stuff>/fanzines/<dir>/<file>.html
            parts=fz.PageName.split("/")
            if len(parts) > 2 and parts[-3:-2][0] == "fanzines":
                url=url+"/../"+"/".join(parts[-2:])+page
            else:
                url=fz.PageName
        return url

    countText=f"{counts.Issuecount:,} issues consisting of {counts.Pagecount:,} pages."
    WriteTable(os.path.join(outputDir, "Chronological_Listing_of_Fanzines.html"),
               datedList,
               lambda fz: UnicodeToHtml(fz.IssueName),
               fButtonText=lambda fz: ChronButtonText(fz),
               fRowHeaderText=lambda fz: (fz.FIS.MonthText+" "+fz.FIS.YearText).strip(),
               fURL=URL,
               countText=countText+"\n"+timestamp+"\n",
               headerFilename='control-Header (Fanzine, chronological).html')
    WriteTable(os.path.join(outputDir, "Chronological Listing of Fanzines.txt"),
               datedList,
               lambda fz: UnicodeToHtml(fz.IssueName),
               fButtonText=lambda fz: ChronButtonText(fz),
               fRowHeaderText=lambda fz: (fz.FIS.MonthText+" "+fz.FIS.YearText).strip(),
               countText=countText+"\n"+timestamp+"\n")
    WriteTable(os.path.join(reportDir, "Undated Fanzine Issues.html"),
               undatedList,
               lambda fz: UnicodeToHtml(fz.IssueName),
               fURL=URL,
               countText=timestamp,
               headerFilename="control-Header (Fanzine, alphabetical).html")

    # Generate a list of all the newszines (in lower case)
    # This takes names from the file control-newszines.txt and adds fanzines tagged as newszines on their series index page

    # Read the control-newszines.txt file
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
    newsCount=FanzineCounts()
    for fz in fanacIssueList:
        if fz.SeriesName.lower() in listOfNewszines and fz.PageName != "":
            newsCount+=fz
            if os.path.splitext(fz.PageName)[1].lower() == ".pdf":
                newsCount.Pdfcount+=1

    # Look for lines in the list of newszines which don't match actual newszines on the site.
    unusedLines=[x for x in listOfNewszines if x.lower() not in listOfNewszines]
    unusedLines=[x+"\n" for x in unusedLines]

    newszines=[x+"\n" for x in listOfNewszines]
    with open(os.path.join(reportDir, "Items identified as newszines.txt"), "w+") as f:
        f.writelines(newszines)
    with open(os.path.join(reportDir, "Unused lines in control-newszines.txt"), "w+") as f:
        f.writelines(unusedLines)

    countText=f"{newsCount.Issuecount:,} issues consisting of {newsCount.Pagecount:,} pages."
    WriteTable(os.path.join(outputDir, "Chronological_Listing_of_Newszines.html"),
               fanacIssueList,
               lambda fz: UnicodeToHtml(fz.IssueName),
               fButtonText=lambda fz: ChronButtonText(fz),
               fRowHeaderText=lambda fz: (fz.FIS.MonthText+" "+fz.FIS.YearText).strip(),
               fURL=URL,
               countText=countText+"\n"+timestamp+"\n",
               headerFilename="control-Header (Newszine).html",
               fSelector=lambda fz: fz.SeriesName.lower() in listOfNewszines)

    # Produce a list of fanzines by title
    def AlphaSortText(fz: FanzineIssueInfo) -> str:
        if fz.SeriesName == "":
            return " "
        # Replace lower case and accented alphas, ignore punctuation, retain digits; the Unidecode is so that things like 'á Bas' sort with A
        out=""
        for c in fz.SeriesName:
            if c.isalpha():
                out+=unidecode.unidecode(c.upper())
            elif c.isdigit():
                out+=c
        return out

    countText=f"{counts.Issuecount:,} issues consisting of {counts.Pagecount:,} pages."
    fanacIssueList.sort(key=lambda elem: elem.FIS.FormatDateForSorting())  # Sorts in place on order in index page, which is usually a good proxy for date
    fanacIssueList.sort(key=lambda elem: AlphaSortText(elem))  # Sorts in place on fanzine's name

    def AlphaButtonText(fz: FanzineIssueInfo) -> str:
        c=AlphaSortText(fz)[0]
        if c == " " or c.isdigit():
            return "*"
        return c

    def Annotate(fz: FanzineIssueInfo) -> str:
        if type(fz) is not FanzineIssueInfo:
            assert ()
        if fz.FIS is None:
            return ""
        if fz.FIS.FD.IsEmpty():
            return ""
        return f"<small>({fz.FIS.FD.LongDates}</small>"

    WriteTable(os.path.join(outputDir, "Alphabetical Listing of Fanzines.txt"),
               fanacIssueList,
               lambda fz: UnicodeToHtml(fz.IssueName),
               fButtonText=lambda fz: fz.SeriesName[0],
               fRowHeaderText=lambda fz: fz.SeriesName,
               countText=countText+"\n"+timestamp+"\n",
               inAlphaOrder=True)
    WriteTable(os.path.join(outputDir, "Alphabetical_Listing_of_Fanzines.html"),
               fanacIssueList,
               lambda fz: UnicodeToHtml(fz.IssueName),
               fButtonText=lambda fz: AlphaButtonText(fz),
               fRowAnnot=lambda fz: Annotate(fz),
               fRowHeaderText=lambda fz: fz.SeriesName,
               fURL=URL,
               countText=countText+"\n"+timestamp+"\n",
               headerFilename="control-Header (Fanzine, alphabetical).html",
               inAlphaOrder=True)

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
               lambda fz: UnicodeToHtml(fz.IssueName),
               fButtonText=lambda fz: fz.SeriesName[0],
               fRowHeaderText=lambda fz: fz.SeriesName,
               countText=timestamp+"\n",
               fSelector=lambda fx: OddNames(fx.IssueName, fx.SeriesName))

    # Count the number of distinct fanzine names (not issue names, but names of runs of fanzines.)
    # Create a set of all fanzines run names (the set to eliminate suploicates) and then get its size.
    fzCount=len(set([fz.SeriesName.lower() for fz in fanacIssueList]))
    nzCount=len(set([fz.SeriesName.lower() for fz in fanacIssueList if fz.SeriesName.lower() in listOfNewszines]))

    # Print to the console and also the statistics file
    Log("\n")
    Log(f"All fanzines: Titles: {fzCount:,}  Issues: {counts.Issuecount:,}  Pages: {counts.Pagecount:,}  PDFs: {counts.Pdfcount:,}")
    Log(f"Newszines:  Titles: {nzCount:,}  Issues: {newsCount.Issuecount:,}  Pages: {newsCount.Pagecount:,}  PDFs: {newsCount.Pdfcount:,}")
    Log(f"All PDF fanzines: Issues: {counts.Pdfcount:,}   Pages: {counts.Pdfpagecount:,}")
    for selectedYear in selectedYears:
        Log(f"{selectedYear[0]} Fanzines: {selectedYear[1]}")
    with open(os.path.join(outputDir, "Statistics.txt"), "w+") as f:
        print(f"All fanzines: Titles: {fzCount:,}  Issues: {counts.Issuecount:,}  Pages: {counts.Pagecount:,}  PDFs: {counts.Pdfcount:,}", file=f)
        print(f"Newszines:  Titles: {nzCount:,}  Issues: {newsCount.Issuecount:,}  Pages: {newsCount.Pagecount:,}  PDFs: {newsCount.Pdfcount:,}", file=f)
        print(f"All PDF fanzines: Issues: {counts.Pdfcount:,}   Pages: {counts.Pdfpagecount:,}", file=f)
        for selectedYear in selectedYears:
            print(f"{selectedYear[0]} Fanzines: {selectedYear[1]}", file=f)

    WriteTable(os.path.join(reportDir, "Fanzines with odd page counts.txt"),
               fanacIssueList,
               lambda fz: UnicodeToHtml(fz.IssueName),
               fButtonText=lambda fz: fz.SeriesName[0],
               fRowHeaderText=lambda fz: fz.SeriesName,
               countText=timestamp,
               fSelector=lambda fz: fz.Pagecount > 250)

    # Now generate a list of fanzine series sorted by country
    # For this, we don't actually want a list of individual issues, so we need to collapse fanacIssueList into a fanzineSeriesList
    # FanacIssueList is a list of FanzineIssueInfo objects.  We will read through them all and create a dictionary keyed by fanzine series name with the country as value.
    class CountryCounts():
        def __init__(self, sl: list[FanzineSeriesInfo], sc: FanzineCounts):
            self.SeriesList: list=sl
            self.SeriesCount: FanzineCounts=sc

    #Country=namedtuple('Country', 'SeriesList SeriesCount')
    fanacSeriesDictByCountry: dict[str, CountryCounts]={}  # Key is country code; value is a tuple of ([FSI], FanzineCounts for country])

    # Run through all the issues in this list of issues
    for issue in fanacIssueList:
        countryName=issue.Locale.CountryName

        # If this is a new country for us, create a new, empty, entry for it
        fanacSeriesDictByCountry.setdefault(countryName, CountryCounts([], FanzineCounts()))  # If needed, add an empty country entry

        # serieslist is the list of fanzine series corresponding to the counts for this CountryCounts object
        # Note that we accumulate the series page and issue totals
        countrycount=fanacSeriesDictByCountry[countryName]

        # Is this new issue from a series that is already in the list for this country?
        # Note that we have defined hash and eq for class FanzineIssueInfo, so two different FanzineIssueInfos can be equal
        if issue.Series not in countrycount.SeriesList:
            series=issue.Series.Deepcopy()
            countrycount.SeriesList.append(series)

        # We want to find the series in the list that matches issue.Series
        series=countrycount.SeriesList[countrycount.SeriesList.index(issue.Series)]
        series+=issue

        # If the directories in the DirURLs match, just add this issue to the existing series totals.
        # If they don't match, just skip it because it's probably one of the doubly-referred-to entries and will be picked up in some other series.
        if issue.Series.DirURL == series.DirURL:
            # serieslist[loc] is a specific series in [country]
            # Update the series by adding the pagecount of this issue to it
            count=countrycount.SeriesCount
            count+=issue
            count.Titlecount+=1
        else:
            Log(f"{issue.Series.DirURL=} != {series.DirURL=}")

    # Next we sort the individual country lists into order by series name
    for ckey, cval in fanacSeriesDictByCountry.items():
        serieslist=cval.SeriesList
        serieslist.sort(key=lambda elem: elem.SeriesName.lower())
        fanacSeriesDictByCountry[ckey]=CountryCounts(serieslist, cval.SeriesCount)  # Sorts in place on fanzine name

    # Take a string which is lower case and turn it to City, State, US sort of capitalization
    def CapIt(s: str) -> str:
        if len(s) == 0:
            return s
        if len(s) == 2:
            return s.upper()
        ret=""
        splits=s.split()
        for split in splits:
            if ret:
                ret+=" "
            ret+=split[0].upper()+split[1:]
        return ret

    # List out the series by country data
    with open(os.path.join(reportDir, "Series by Country.txt"), "w+") as f:
        keys=list(fanacSeriesDictByCountry.keys())
        keys.sort()  # We want to list the countries in alphabetical order
        for key in keys:
            val=fanacSeriesDictByCountry[key]
            k=key if len(key.strip()) > 0 else "<no country>"
            print(f"\n{CapIt(k)}   {len(val.SeriesList)} titles,  {val.SeriesCount.Issuecount} issues,  and {val.SeriesCount.Pagecount} pages", file=f)
            for series in val.SeriesList:
                if series.DisplayName != "":
                    print(f"    {series.DisplayName}    ({series.Issuecount} issues, {series.Pagecount} pages)", file=f)
                    Log(f"    {series.DisplayName}    ({series.Issuecount} issues, {series.Pagecount} pages)")
                else:
                    print(f"    {series.DisplayName}    ({series.Issuecount} issues, {series.Pagecount} pages)", file=f)
                    Log(f"    {series.DisplayName}    ({series.Issuecount} issues, {series.Pagecount} pages)")

    # Now create a properly ordered flat list suitable for WriteTable
    fanacFanzineSeriesListByCountry: list[tuple[str, FanzineCounts, str]]=[]
    for countryName, countryEntries in fanacSeriesDictByCountry.items():
        for v in countryEntries.SeriesList:
            fanacFanzineSeriesListByCountry.append((countryName, countryEntries.SeriesCount, v))  # (country, countryCount, series)
    fanacFanzineSeriesListByCountry.sort(key=lambda elem: RemoveAccents(RemoveArticles(elem[2].DisplayName.lower())).lower())
    fanacFanzineSeriesListByCountry.sort(key=lambda elem: elem[0].lower())

    # Provides the annotation for rows in the following output table
    def plural(i: int) -> str:
        return "s" if i > 1 else ""

    def Annotate(elem: FanzineCounts) -> str:
        s=""
        if elem.Titlecount > 0:
            s=str(elem.Titlecount)+" title"+plural(elem.Titlecount)+", "
        i=elem.Issuecount
        p=elem.Pagecount
        if i > 0:
            s+=str(i)+" issue"+plural(i)+", "
            s+=str(p)+" page"+plural(p)
        if s:
            s="("+s+")"
        return s

    WriteTable(os.path.join(outputDir, "Series_by_Country.html"),
               fanacFanzineSeriesListByCountry,
               lambda elem: UnicodeToHtml(elem[2].DisplayName)+(("| <small>("+elem[2].Editor+")</small>") if elem[2].Editor != "" else ""),
               fRowHeaderText=lambda elem: CapIt(elem[0]),
               fURL=lambda elem: elem[2].DirURL,
               fButtonText=lambda elem: CapIt(elem[0]),
               fRowAnnot=lambda elem: f"<small>{Annotate(elem[2])}</small>",
               fHeaderAnnot=lambda elem: f"<small>{Annotate(elem[1])}</small>",
               countText=timestamp,
               headerFilename="control-Header (Fanzine, by country).html",
               inAlphaOrder=True)

    # Compute counts of issues and series by decade.
    # We get the issue numbers by simply going through the list and adding one to the appropriate decade.
    # For series, we create a set of series found for that decade

    # issueDecadeCount and seriesDecadeCount are  dictionaries keyed by decade: 190, 191, ...199, 200...
    # For issueDecadeCount, the value is a count for that decade
    # For seriesDecadeCount, the value is a set of series names which we will count in the end.
    issueDecadeCount: dict[int, int]={}
    seriesDecadeCount: dict[int, Set[str]]={}
    for issue in fanacIssueList:
        year=0
        if issue.FIS is not None and issue.FIS.Year is not None:
            year=issue.FIS.Year
        decade=math.floor(year/10)

        issueDecadeCount.setdefault(decade, 0)
        seriesDecadeCount.setdefault(decade, set())

        issueDecadeCount[decade]+=1
        seriesDecadeCount[decade].add(issue.SeriesName)

    # Print the report
    with open(os.path.join(reportDir, "Decade counts.txt"), "w+") as f:
        f.write(str(datetime.date.today())+"\n")
        f.write("Counts of fanzines and fanzine series by decade\n\n")
        f.write(" Decade  Series  Issues\n")
        decades=sorted([x for x in issueDecadeCount.keys()])
        for decade in decades:
            counts=f"{len(seriesDecadeCount[decade]):5}   {issueDecadeCount[decade]:5}"
            if decade == 0:
                print(f"undated   {counts}", file=f)
            else:
                print(f"  {decade:3}0s   {counts}", file=f)

    Log("FanacAnalyzer has Completed.")

    LogClose()
# End of main()
##################################################################
##################################################################
##################################################################


# ====================================================================================
# Read fanac.org/fanzines/Classic_Fanzines.html amd /Modern_Fanzines.html
# Read the table to get a list of all the fanzines on Fanac.org
# Return a list of tuples (name on page, name of directory)
#       The name on page is the display named used in the fanzine series tables (e.g., "Classic Fanzines")
#       The name of directory is the name of the directory pointed to

def ReadAllFanacFanzineMainPages() -> list[tuple[str, str]]:
    Log("----Begin reading Classic and Modern tables")
    # This is a list of fanzines on Fanac.org
    # Each item is a tuple of (compressed name,  link name,  link url)
    fanacFanzineDirectoriesList: list[tuple[str, str]]=[]
    directories=ReadList("control-topleveldirectories.txt")
    for dirs in directories:
        ReadModernOrClassicTable(fanacFanzineDirectoriesList, dirs)

    Log("----Done reading Classic and Modern tables")
    return fanacFanzineDirectoriesList


# ======================================================================
# Read one of the main fanzine directory listings and append all the fanzines directories found to the dictionary
def ReadModernOrClassicTable(fanacFanzineDirectoriesList: list[tuple[str, str]], url: str) -> None:
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


def ReadFile(filename: str) -> list[str]:
    try:
        with open(filename, "r") as f2:
            return f2.readlines()
    except:
        # If the expected control header is unavailable, bail out. Otherwise return an empty list.
        LogFailureAndRaiseIfMissing(filename)
    return []

#================================================================================
# fRowHeaderText and fRowBodyText and fSelector are all lambdas
#   fSelector decides if this fanzines is to be listed and returns True for fanzines to be listed, and False for ones to be skipped. (If None, nothing will be skipped)
#   fButtonText operates on an issue and selects the character (or whatever) that will be used for button grouping
#   fRowHeaderText and fRowBodyText are functions which pull information out of a fanzineIssue from fanzineIssueList
#   fRowHeaderText is the item used to decide when to start a new subsection
#   fRowBodyText is what is listed in the subsection
def WriteTable(filename: str,
               fanacIssueList: list,  # The sorted input list
               fRowBodyText: Callable[[Any], str],  # Function to supply the row's body text
               fButtonText: Optional[Callable[[Any], str]]=None,  # Function to supply the button text
               fRowHeaderText: Optional[Callable[[Any], str]]=None,  # Function to supply the header text
               fURL: Optional[Callable[[Any], str]]=None,  # Function to supply the URL
               fDirURL: Optional[Callable[[Any], str]]=None,  # Function to supply the directory or root URL
               fRowAnnot: Optional[Callable[[Any], str]]=None,  # Function to supply annotation to the rows
               fHeaderAnnot: Optional[Callable[[Any], str]] = None,  # Function to supply annotation to the headers
               countText: str="",
               headerFilename: str="",
               fSelector: Optional[Callable[[Any], bool]]=None,
               inAlphaOrder: bool=False)\
                -> None:
    f: TextIO=open(filename, "w+")

    #....... Header .......
    # Filename can end in ".html" or ".txt" and we output html or plain text accordingly
    html=filename.lower().endswith(".html")
    if html:
        # When we're generating HTML output, we need to include a header.
        # It will be a combination of the contents of "control-Header (basic).html" with headerInfoFilename
        basicHeadertext=ReadFile("control-Header (basic).html")
        if not basicHeadertext:
            return

        # Read the specialized control.html file for this type of report
        specialText=ReadFile(headerFilename)
        if specialText:
            specialText=[s for s in specialText if len(s) > 0 and s[0] !="#"]   # Ignore comments
            title=specialText[0]
            del specialText[0]

            # Do the substitutions
            for i in range(0, len(basicHeadertext)):
                if basicHeadertext[i].strip() == "<title>title</title>":
                    basicHeadertext[i]=f"<title>{title}</title>"
                if basicHeadertext[i].strip() == "<h1>title</h1>":
                    basicHeadertext[i]=f"<h1>{title}</h1>"
            basicHeadertext.extend(specialText)

        f.writelines(basicHeadertext)

    if countText:
        if html:
            countText=countText.replace("\n", "<p>")
            countText=f"<p>{countText}</p>\n"
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
            if buttonlist:
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

    lastRowHeader: str=""
    lastButtonLinkString: str=""
    for fz in fanacIssueList:
        # Do we skip this fanzine
        if fSelector is not None and not fSelector(fz):
            continue
        if html and fURL is not None and fURL(fz) is None:
            continue

        # Get the button link string, to see if we have a new decade (or 1st letter) and need to create a new jump anchor
        buttonLinkString: str=""
        if html:
            if fButtonText is not None:
                if fButtonText(fz) is not None:
                    buttonLinkString=fButtonText(fz)

        # Start a new row
        # Deal with Column 1
        if fRowHeaderText is not None and lastRowHeader != fRowHeaderText(fz):
            if lastRowHeader:  # If this is not the first sub-box, we must end the previous sub-box by ending its col 2
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
                if inAlphaOrder and fDirURL is not None:
                    f.write(FormatLink(fDirURL(fz), UnicodeToHtml(lastRowHeader)))
                else:
                    f.write(UnicodeToHtml(lastRowHeader))
                if fHeaderAnnot is not None and fHeaderAnnot(fz) is not None:
                    f.write("&nbsp;&nbsp;&nbsp;&nbsp;"+fHeaderAnnot(fz))
                f.write('</div>\n')
                f.write('    <div class=col-md-9>\n') # Start col 2
            else:
                f.write("\n"+lastRowHeader)
                if fHeaderAnnot is not None and fHeaderAnnot(fz) is not None:
                    f.write("&nbsp;&nbsp;&nbsp;&nbsp;"+RemoveAllHTMLTags2(fHeaderAnnot(fz)))
                f.write("\n")


        # Deal with Column 2
        # The hyperlink goes in column 2
        # There are two kinds of hyperlink: Those with just a filename (xyz.html) and those with a full URL (http://xxx.vvv.zzz.html)
        # The former are easy, but the latter need to be processed
        bodytext=fRowBodyText(fz)
        if html:
            if fURL is not None:
                # if there is a pipe character in the string, we only link the part before the pipe and delete the pipe
                splitext=bodytext.split("|", 2)
                if len(splitext) == 2:
                    f.write('        '+FormatLink(fURL(fz), splitext[0])+splitext[1])
                else:
                    f.write('        '+FormatLink(fURL(fz), bodytext))
            else:
                f.write('        '+fz)
            if inAlphaOrder and fRowAnnot is not None and fRowAnnot(fz) is not None:
                    f.write("&nbsp;&nbsp;&nbsp;&nbsp;"+ fRowAnnot(fz))
            f.write('<br>\n')
        else:
            bodytext=bodytext.replace("|", "", 1)  # Ignore the first  embedded "|" character
            f.write("   "+bodytext+"\n")

    #....... Cleanup .......
    # And end everything
    if html:
        f.write('</div>\n</div>\n')
        f.writelines(ReadFile("control-Default.Footer"))
    f.close()


# -------------------------------------------------------------------------
# We have a name and a dirname from the fanac.org Classic and Modern pages.
# The dirname *might* be a URL in which case it needs to be handled as a foreign directory reference
def AddFanacDirectory(fanacFanzineDirectoriesList: list[tuple[str, str]], name: str, dirname: str) -> None:

    # We don't want to add duplicates. A duplicate is one which has the same dirname, even if the text pointing to it is different.
    dups=[e2 for e1, e2 in fanacFanzineDirectoriesList if e2 == dirname]
    if dups:
        Log(f"   duplicate: {name=}  {dirname=}")
        return

    if dirname.startswith("http"):
        Log(f"    ignored, because is HTML: {dirname}")
        return

    # Add name and directory reference
    Log(f"   added to fanacFanzineDirectories:  {name=}  {dirname=}")
    fanacFanzineDirectoriesList.append((name, dirname))
    return


# Run main()
if __name__ == "__main__":
    main()