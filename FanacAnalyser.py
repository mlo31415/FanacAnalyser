from typing import Callable, Set
from time import localtime, strftime

import requests
import os
import sys
import re
import math
import datetime
from unidecode import unidecode
from bs4 import BeautifulSoup
import csv

import FanacOrgReaders

from Settings import Settings
from FanzineIssueSpecPackage import FanzineIssueInfo, FanzineCounts, FanzineDate
from Log import Log, LogOpen, LogClose, LogFailureAndRaiseIfMissing, LogError
from HelpersPackage import ReadList, FormatLink, UnicodeToHtml, RemoveArticles, CaseInsensitiveCompare
from HelpersPackage import RemoveAllHTMLTags2, FlattenPersonsNameForSorting, FlattenTextForSorting
from HelpersPackage import UnscrambleListOfNames, Pluralize
from HelpersPackage import ReadListAsParmDict


def main():
    LogOpen("Log - Fanac Analyzer Detailed Analysis Log.txt", "Log - Fanac Analyzer Error Log.txt")
    Log("Started")

    Settings().Load("parameters.txt", MustExist=True)

    # Read the command line argument, if any, which will override rootDir
    rootDir="."
    if len(sys.argv) > 1:
        rootDir=sys.argv[1]
    rootDir=Settings().Get("root directory", rootDir)   # So will a value in the parameters file

    # Make sure the root directory exists
    if not os.path.isdir(rootDir):
        os.mkdir(rootDir)
    Log("Root directory '"+rootDir+"' set")

    # Create a Reports directory if needed.
    reportDir=Settings().Get("Report Directory", "Reports")
    reportFilePath=str(os.path.join(rootDir, reportDir))
    if not os.path.isdir(reportFilePath):
        try:
            os.mkdir(reportFilePath)
        except Exception as e:
            LogError(f"***Fatal Error: Attempt to create directory {reportFilePath} yields exception: {e}")
            exit(1)
    if not os.path.isdir(os.path.join(reportFilePath, "Reports by year")):
        os.mkdir(os.path.join(reportFilePath, "Reports by year"))
    Log("Report directory '"+reportFilePath+"' created")

    # See if the file 'People Canonical Names.txt' exists.  If it does, read it.
    peopleCanonicalNames={}
    filepathname=os.path.join(rootDir, "People Canonical Names.txt") # This file is created by FancyAnalyzer and must be dragged over to FanacAnalyzer's directories
    if os.path.exists(filepathname):
        with open(filepathname, "r" ,encoding='utf8') as f:
            for line in f:
                loc=line.find("-->")
                if loc > 0:
                    n1=line[:loc-1].strip()
                    n2=line[loc+3:].strip()
                    peopleCanonicalNames[n1]=n2

    # Read the fanac.org fanzine index page structures and produce a list of all fanzine series directories
    fanacFanzineDirectories=ReadAllFanacFanzineMainPages()

    # Read the directories list and produce a list of all fanzine issues
    fanacIssueList=FanacOrgReaders.ReadFanacFanzineIssues(rootDir, fanacFanzineDirectories)

    # Remove issues which have entries, but don't actually point to anything.
    fanacIssueList=[x for x in fanacIssueList if x.PageFilename != ""]
    if len(fanacIssueList) == 0:
        Log("Exiting: No fanzines found")
        return

    # Sort the list of all fanzines issues by fanzine series name
    fanacIssueList.sort(key=lambda elem: RemoveArticles(unidecode(elem.SeriesName.casefold())))  # Sorts in place on fanzine name

    def NoNone(s: str) -> str:
        if s is None:
            return ""
        return s

    # Read the control-year.txt file to get the year(s) to be dumped out
    selectedYears: list[tuple[int, int]]=[]
    for year in range(1926, 2023):
        yearCount=0
        selected: list[tuple[str, FanzineDate | None, str, str]]=[]
        for fz in fanacIssueList:
            if fz.FIS.Year == year:
                #out+=f"|| {fz.IssueName} || {NoNone(str(fz.FIS))} || {fz.DirURL} || {fz.PageFilename} ||\n"
                selected.append((fz.IssueName, fz.FIS.FD, fz.DirURL, fz.PageFilename))
                yearCount+=1
        if yearCount > 0:
            selected.sort(key=lambda x: x[1])
            with open(os.path.join(os.path.join(reportFilePath, "Reports by year"), f"{year} fanac.org Fanzines.txt"), "w+") as f:
                for sel in selected:
                    f.write(f"{sel[0]} || {NoNone(str(sel[1]))} || {sel[2]} || {sel[3]}\n")
            selectedYears.append((year, yearCount))  # Create a list of tuples (selected year, count)

    # Count the number of pages, issues and PDFs
    ignorePageCountErrors=ReadList(os.path.join(rootDir, "control-Ignore Page Count Errors.txt"))
    countsGlobal=FanzineCounts()
    for fzi in fanacIssueList:
        if fzi.DirURL != "":
            countsGlobal+=fzi.Pagecount
            if os.path.splitext(fzi.PageFilename)[1].lower() == ".pdf":
                countsGlobal.Pdfcount+=1
                countsGlobal.Pdfpagecount+=fzi.Pagecount
            if fzi.Pagecount == 0 and len(ignorePageCountErrors)> 0 and fzi.SeriesName not in ignorePageCountErrors:
                Log(f"{fzi.IssueName} has no page count: {fzi}")

    # Re-run the previous producing a counts diagnostic file
    with open(os.path.join(reportFilePath, "Counts diagnostics.txt"), "w") as f:
        countsSeries=FanzineCounts()
        lines: [str]=[]  # We want to print everything about this series once we have completed going through the series
        oldseries=fanacIssueList[0].SeriesName
        for fzi in fanacIssueList:

            if fzi.SeriesName != oldseries: # and len(lines) > 0:
                # Dump what we know about the old series
                print(f"{oldseries}      {countsSeries.Issuecount} issues   {countsSeries.Pagecount} pages  ", file=f)
                for line in lines:
                    print(line, file=f)
                lines: [str]=[]
                countsSeries=FanzineCounts()
            oldseries=fzi.SeriesName # Safe to do because any changes if fz.SeriesName was just handled

            if fzi.DirURL != "":
                countsSeries+=fzi.Pagecount
                if os.path.splitext(fzi.PageFilename)[1].lower() == ".pdf":
                    countsSeries.Pdfcount+=1
                    countsSeries.Pdfpagecount+=fzi.Pagecount
                lines.append(f"      {fzi.Pagecount:<4} {fzi.IssueName}")
            else:
                lines.append(f"Skipped for empty DirURL: {fzi.SeriesName}/{fzi.IssueName}")

        if len(lines) > 0:
            # Dump what we know about the old series
            print(f"{oldseries}  {countsSeries.Issuecount} issues   {countsSeries.Pagecount} pages  ", file=f)
            for line in lines:
                print(line, file=f)

    # Produce a report on the non-PDFed fanzines
    with open(os.path.join(reportFilePath, "Fanzines which are not PDFs.txt"), "w") as f:
        for fzi in fanacIssueList:
            if not fzi.URL.lower().endswith(".pdf"):
                print(f"{fzi.DirURL}/{fzi.IssueName}", file=f)



    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # Produce various lists of fanzines for upcoming WriteTables
    # List sorted alphabetically, and by date within that
    fanacIssueList.sort(key=lambda elem: FlattenTextForSorting(elem.IssueName))  # Sorts in place on fanzine's name with leading articles suppressed
    fanacIssueList.sort(key=lambda elem: elem.FIS.FormatDateForSorting())

    timestamp="Indexed as of "+strftime("%Y-%m-%d %H:%M:%S", localtime())+" EST"
    topcounttext=f"{countsGlobal.Issuecount:,} issues consisting of {countsGlobal.Pagecount:,} pages."

    # List of dated issues
    with open(os.path.join(reportFilePath, "Fanzines in date order.txt"), "w") as f:
        for fzi in fanacIssueList:
            f.write(f"{fzi.FIS.DateStr} -- {fzi} {fzi.Pagecount}pp   {fzi.FanzineType}   {fzi.Series.Keywords}\n")

    # Note that because things are sorted by date, for a given month+year, things with no day sort before things with a day
    # List of dated issues
    datedList=[f for f in fanacIssueList if not f.FIS.IsEmpty()]
    WriteHTMLTable(os.path.join(reportFilePath, "Chronological_Listing_of_Fanzines.html"),
                   datedList,
                   fURL=URL,
                   fButtonText=lambda fz: ChronButtonText(fz),
                    #
                   fRowHeaderText=lambda fz: fz.FIS.MonthYear,
                   includeRowHeaderCounts=True,
                    #
                   fRowBodyText=lambda fz: UnicodeToHtml(fz.IssueName),
                   fRowBodyAnnot=lambda fz: f"ed. {fz.Editor}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{Pluralize(fz.Pagecount, 'page')}",
                    #
                   topCountText=topcounttext+"\n"+timestamp+"\n",
                   #
                   headerFilename='control-Header (Fanzine, chronological).html')

    WriteTxtTable(os.path.join(reportFilePath, "Chronological Listing of Fanzines.txt"),
                  datedList,
                  fRowBodyText=lambda fz: fz.IssueName,
                  fRowHeaderText=lambda fz: fz.FIS.MonthYear,
                  topCountText=topcounttext+"\n"+timestamp+"\n")
    # List of undated issues
    undatedList=[f for f in fanacIssueList if f.FIS.IsEmpty()]
    WriteHTMLTable(os.path.join(reportFilePath, "Undated Fanzine Issues.html"),
                   undatedList,
                   fRowBodyText=lambda fz: UnicodeToHtml(fz.IssueName),
                   fRowHeaderText=lambda fz: "fRowHeaderText fake lambda",
                   fURL=URL,
                   topCountText=timestamp,
                   headerFilename="control-Header (basic).html")


    # Generate a list of all the newszines (in lower case)
    # This takes names from the file control-newszines.txt and adds fanzines tagged as newszines on their series index page

    # Read the control-newszines.txt file
    newszinesSet=set([x.casefold() for x in ReadList(os.path.join(rootDir, "control-newszines.txt"), isFatal=True)])

    # Add in the newszines discovered in the <h2> blocks
    newszinesFromH2Set=set([fii.SeriesName.casefold() for fii in fanacIssueList if "newszine" in fii.Taglist])
    with open(os.path.join(reportFilePath, "Items identified as newszines by H2 tags.txt"), "w+") as f:
        newszinesFromH2List=sorted(list(newszinesFromH2Set))
        for nz in newszinesFromH2List:
            f.write(nz+"\n")

    newszinesSet=newszinesSet.union(newszinesFromH2Set)

    # Make up a lists of newszines and non-newszines
    allzinesSet=set([fx.SeriesName.casefold() for fx in fanacIssueList])

    with open(os.path.join(reportFilePath, "Items identified as non-newszines.txt"), "w+") as f:
        nonNewszines=sorted(list(allzinesSet.difference(newszinesSet)))
        for nnz in nonNewszines:
            f.write(nnz+"\n")

    listOfNewszines=sorted(list(newszinesSet))
    for fz in fanacIssueList:
        if fz.SeriesName.casefold() in listOfNewszines:
            fz.FanzineType="newszine"

    # Count the number of issue and pages of all fanzines and of just newszines
    newsCount=FanzineCounts()
    for fz in fanacIssueList:
        if fz.FanzineType == "newszine" and fz.PageFilename != "":
            newsCount+=fz
            if os.path.splitext(fz.PageFilename)[1].lower() == ".pdf":
                newsCount.Pdfcount+=1

    newszines=[x+"\n" for x in listOfNewszines]
    with open(os.path.join(reportFilePath, "Items identified as newszines.txt"), "w+") as f:
        f.writelines(newszines)

    newscountText=f"{newsCount.Issuecount:,} issues consisting of {newsCount.Pagecount:,} pages."
    WriteHTMLTable(os.path.join(reportFilePath, "Chronological_Listing_of_Newszines.html"),
                   fanacIssueList,
                   fURL=URL,
                   fRowHeaderText=lambda fz: (fz.FIS.MonthText+" "+fz.FIS.YearText).strip(),
                   fRowHeaderText=lambda fz: fz.FIS.MonthYear,
                   fButtonText=lambda fz: ChronButtonText(fz),
                   fRowBodyText=lambda fz: UnicodeToHtml(fz.IssueName),
                   fRowBodyAnnot=lambda fz: f"ed. {fz.Editor}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{Pluralize(fz.Pagecount, 'page')}",
                   topCountText=newscountText+"\n"+timestamp+"\n",
                   headerFilename="control-Header (Newszine).html")

    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # Generate Alphabetic lists by Fanzine title
    topcounttext=f"{countsGlobal.Issuecount:,} issues consisting of {countsGlobal.Pagecount:,} pages."

    # Generate lists by title
    # For this pair of reports, we need to create a modified fanacIssueList, duplicating entries for all issues with multiple titles
    fanacIssueListByTitle: list[FanzineIssueInfo]=[]
    for fz in fanacIssueList:
        # We expand this FanzineIssueInfo into one for each title.
        # We store the original title list in the _Temp member used for such kludgey purposes
        names=[x.strip() for x in fz.SeriesName.split(";")]
        if len(names) > 1:
            for name in names:
                fz2=fz.DeepCopy()       # We do this so that the diddling we do to create multiple entries for the same fanzine does not impact fanacIssueList
                fz2.Temp=fz.SeriesName
                sn2=fz2.Series.Deepcopy()
                sn2.SeriesName=name.strip()
                fz2.Series=sn2
                fanacIssueListByTitle.append(fz2)
        else:
            if len(fz.SeriesName) > 0:  # In a by-title listing, missing titles are uninteresting
                fanacIssueListByTitle.append(fz)

    fanacIssueListByTitle.sort(key=lambda elem: elem.FIS.FormatDateForSorting())  # Sorts in place on order in index page, which is usually a good proxy for date
    def MessySort(x: FanzineIssueInfo): # This handles the fact that MT Void is scattered among many pages, so position does nto work for it.  Ugly.
        if "MT Void" in x.SeriesName:
            return x.FIS.FormatDateForSorting()
        return f"{x.Position:0>5}"
    fanacIssueListByTitle.sort(key=MessySort)
    fanacIssueListByTitle.sort(key=lambda elem:FlattenTextForSorting(elem.SeriesName+" "+elem.SeriesEditor, RemoveLeadingArticles=True)) # Sorts in place on fanzine's Series name+Series title (added to disambiguate similarly-named fanzines


    WriteTxtTable(os.path.join(reportFilePath, "Alphabetical Listing of Fanzines.txt"),
                  fanacIssueListByTitle,
                  fRowBodyText=lambda fz: fz.IssueName,
                  fRowHeaderText=lambda fz: fz.SeriesName,
                  topCountText=topcounttext+"\n"+timestamp+"\n")
    WriteHTMLTable(os.path.join(reportFilePath, "Alphabetical_Listing_of_Fanzines.html"),
                   fanacIssueListByTitle,
                   fButtonText=lambda fz: AlphaButtonText(fz),
                   fDirURL=lambda fz: fz.DirURL,
                   fURL=URL,
                   fRowHeaderSelect=lambda fz: fz.SeriesName+fz.SeriesEditor,
                   fRowHeaderText=lambda fz: fz.SeriesName,
                   fRowHeaderAnnot=lambda fz: f"<br><small>{fz.SeriesEditor}</small>",
                   fRowBodyText=lambda fz: UnicodeToHtml(fz.IssueName),
                   fRowBodyAnnot=lambda fz: AnnotateDate(fz),
                   topCountText=topcounttext+"\n"+timestamp+"\n",
                   headerFilename="control-Header (Fanzine, alphabetical).html",
                   inAlphaOrder=True)


    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # Generate a list of fanzine series sorted by country
    # For this, we don't actually want a list of individual issues, so we need to collapse fanacIssueList into a fanzineSeriesList
    # FanacIssueList is a list of FanzineIssueInfo objects.  We will read through them all and create a dictionary keyed by fanzine series name with the country as value.


    # Create a properly ordered flat list suitable for WriteTable
    fanacIssueList.sort(key=lambda elem: FlattenTextForSorting(elem.Series.DisplayName))   # Sort by series name
    fanacIssueList.sort(key=lambda elem: elem.Locale.CountryName.lower())      # Sort by country

    WriteHTMLTable(os.path.join(reportFilePath, "Series_by_Country.html"),
                   fanacIssueList,
                   fURL=lambda elem: elem.Series.DirURL,
                   fButtonText=lambda elem: CapIt(elem.Locale.CountryName),
                   #
                   fRowHeaderText=lambda elem: CapIt(elem.Locale.CountryName),
                   includeRowHeaderCounts=True,
                   #
                   fRowBodyText=lambda elem: UnicodeToHtml(elem.Series.DisplayName),
                   fRowBodyAnnot=lambda elem: UnicodeToHtml(elem.Editor),
                   fRowBodySelect=lambda elem: elem.Series.DisplayName,
                   showDuplicateBodyRows=False,
                   #
                   topCountText=timestamp,
                   headerFilename="control-Header (Fanzine, by country).html",
                   inAlphaOrder=True)



    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # Generate lists by editor
    # For this pair of reports, we need to create a modified fanacIssueList, duplicating entries for all issues with multiple editors
    fanacIssueListByEditor: list[FanzineIssueInfo]=[]
    for fz in fanacIssueList:
        # We expand this FanzineIssueInfo into one for each editor.
        # We store the original editor list in the _Temp member used for such kludgey purposes
        eds=UnscrambleListOfNames(fz.Editor)
        for i, ed in enumerate(eds):
            if ed in peopleCanonicalNames:
                eds[i]=peopleCanonicalNames[ed]

        if len(eds) > 1:
            for ed in eds:
                fz2=fz.DeepCopy()
                fz2.Temp=fz.Editor
                fz2.Editor=ed.strip()
                fanacIssueListByEditor.append(fz2)
        else:
            if len(fz.Editor) > 0:      # In a by-editor listing, missing editors are uninteresting
                fz.Editor=eds[0].strip()
                fanacIssueListByEditor.append(fz)

    # Sort the Alphabetic lists by Editor
    fanacIssueListByEditor.sort(key=lambda elem: elem.FIS.FormatDateForSorting())
    fanacIssueListByEditor.sort(key=lambda elem: FlattenTextForSorting(elem.SeriesName))  # Sorts in place on fanzine's name with leading articles suppressed
    fanacIssueListByEditor.sort(key=lambda elem: FlattenPersonsNameForSorting(elem.Editor))  # Sorts by editor

    WriteTxtTable(os.path.join(reportFilePath, "Alphabetical Listing of Fanzines by Editor.txt"),
                  fanacIssueListByEditor,
                  fRowBodyText=lambda fz: fz.IssueName,
                  fRowHeaderText=lambda fz: fz.Editor,
                  topCountText=topcounttext+"\n"+timestamp+"\n")
    WriteHTMLTable(os.path.join(reportFilePath, "Alphabetical_Listing_of_Fanzines_by_Editor.html"),
                   fanacIssueListByEditor,
                   fURL=lambda elem: elem.URL,
                   fButtonText=lambda fz: FlattenPersonsNameForSorting(fz.Editor)[0].upper(),
                   #
                   fRowHeaderText=lambda fz: fz.Editor,
                   fCompareRowHeaderText=lambda s1, s2: CompareIgnorePunctAndCase(FlattenPersonsNameForSorting(s1), FlattenPersonsNameForSorting(s2)),
                   includeRowHeaderCounts=True,
                   includeRowTitleCount=True,
                   #
                   fRowBodyText=lambda fz: UnicodeToHtml(fz.IssueName),
                   fRowBodyAnnot=lambda fz: Pluralize(fz.Pagecount, 'page', Spacechar="&nbsp;"),
                   #
                   topCountText=topcounttext+"\n"+timestamp+"\n",
                   headerFilename="control-Header (Fanzine, by editor).html",
                   inAlphaOrder=True)

    WriteHTMLTable(os.path.join(reportFilePath, "Alphabetical_Listing_of_Fanzine_Series_by_Editor.html"),
                   fanacIssueListByEditor,
                   fURL=lambda fz: fz.Series.DirURL,
                   fButtonText=lambda fz: FlattenPersonsNameForSorting(fz.Editor)[0].upper(),
                   #
                   fRowHeaderText=lambda fz: fz.Editor,
                   fCompareRowHeaderText=lambda s1, s2: CompareIgnorePunctAndCase(FlattenPersonsNameForSorting(s1), FlattenPersonsNameForSorting(s2)),
                   includeRowHeaderCounts=True,
                   includeRowTitleCount=True,
                   #
                   fRowBodyText=lambda fz: UnicodeToHtml(fz.SeriesName),
                   fRowBodySelect=lambda fz: UnicodeToHtml(fz.Series.SeriesName+fz.Editor),
                   showDuplicateBodyRows=False,
                   #
                   topCountText=topcounttext+"\n"+timestamp+"\n",
                   headerFilename="control-Header (Fanzine, by editor).html",
                   inAlphaOrder=True)

    # Sort the Alphabetic lists by Editor, but with fanzines in date order
    fanacIssueListByEditor.sort(key=lambda elem: elem.FIS.FormatDateForSorting())
    fanacIssueListByEditor.sort(key=lambda elem: FlattenPersonsNameForSorting(elem.Editor))  # Sorts by editor

    WriteHTMLTable(os.path.join(reportFilePath, "Chronological_Listing_of_Fanzines_by_Editor.html"),
                   fanacIssueListByEditor,
                   fURL=lambda elem: elem.URL,
                   fButtonText=lambda fz: FlattenPersonsNameForSorting(fz.Editor)[0].upper(),
                   #
                   fRowHeaderText=lambda fz: fz.Editor,
                   fCompareRowHeaderText=lambda s1, s2: CompareIgnorePunctAndCase(FlattenPersonsNameForSorting(s1), FlattenPersonsNameForSorting(s2)),
                   includeRowHeaderCounts=True,
                   #
                   fRowBodyText=lambda fz: UnicodeToHtml(fz.IssueName),
                   fRowBodyAnnot=lambda fz: f"{fz.FIS.FD};&nbsp;&nbsp; {Pluralize(fz.Pagecount, 'page', Spacechar='&nbsp;')}",
                   #
                   topCountText=topcounttext+"\n"+timestamp+"\n",
                   headerFilename="control-Header (Fanzine, by editor).html",
                   inAlphaOrder=True)

    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # Debug: Generate lists of fanzines with odd names.  These should be checked for errors.
    # Note that we're being real simple and picky here!

    # Read through the alphabetic list and generate a flag file of cases where the issue name doesn't match the serial name
    # This function is used only in the lambda expression following immediately afterwards.
    def OddNames(n1: str, n2: str) -> bool:
        n1=RemoveArticles(n1).casefold().strip()
        n2=RemoveArticles(n2).casefold().strip()
        # We'd like them to match to the length of the shorter name
        length=min(len(n1), len(n2))
        return n1[:length] != n2[:length]

    WriteTxtTable(os.path.join(reportFilePath, "Fanzines with odd names.txt"),
                  fanacIssueList,
                  fRowBodyText=lambda fz: fz.IssueName,
                  fRowHeaderText=lambda fz: fz.SeriesName,
                  topCountText=timestamp+"\n",
                  fSelector=lambda fx: OddNames(fx.IssueName, fx.SeriesName))


    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # More general stuff: statistics and the like
    # Count the number of distinct fanzine names (not issue names, but names of runs of fanzines.)
    # Create a set of all fanzines run names (the set to eliminate suploicates) and then get its size.
    fzCount=len(set([fz.SeriesName.casefold() for fz in fanacIssueList]))
    nzCount=len(set([fz.SeriesName.casefold() for fz in fanacIssueList if fz.FanzineType == "newszine"]))

    # Print to the console and also the statistics file
    Log("\n")
    Log(f"All fanzines: Titles: {fzCount:,}  Issues: {countsGlobal.Issuecount:,}  Pages: {countsGlobal.Pagecount:,}  PDFs: {countsGlobal.Pdfcount:,}")
    Log(f"Newszines:  Titles: {nzCount:,}  Issues: {newsCount.Issuecount:,}  Pages: {newsCount.Pagecount:,}  PDFs: {newsCount.Pdfcount:,}")
    Log(f"All PDF fanzines: Issues: {countsGlobal.Pdfcount:,}   Pages: {countsGlobal.Pdfpagecount:,}")
    for selectedYear in selectedYears:
        Log(f"{selectedYear[0]} Fanzines: {selectedYear[1]}")

    with open(os.path.join(reportFilePath, "Statistics.txt"), "w+") as f:
        print(timestamp)
        print(f"All fanzines: Titles: {fzCount:,}  Issues: {countsGlobal.Issuecount:,}  Pages: {countsGlobal.Pagecount:,}  PDFs: {countsGlobal.Pdfcount:,}", file=f)
        print(f"Newszines:  Titles: {nzCount:,}  Issues: {newsCount.Issuecount:,}  Pages: {newsCount.Pagecount:,}  PDFs: {newsCount.Pdfcount:,}", file=f)
        print(f"All PDF fanzines: Issues: {countsGlobal.Pdfcount:,}   Pages: {countsGlobal.Pdfpagecount:,}", file=f)
        for selectedYear in selectedYears:
            print(f"{selectedYear[0]} Fanzines: {selectedYear[1]}", file=f)


    WriteTxtTable(os.path.join(reportFilePath, "Fanzines with odd page counts.txt"),
                  fanacIssueList,
                  fRowBodyText=lambda fz: fz.IssueName,
                  fRowHeaderText=lambda fz: fz.SeriesName,
                  topCountText=timestamp,
                  fSelector=lambda fz: fz.Pagecount > 250)


    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
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
    with open(os.path.join(reportFilePath, "Decade counts.txt"), "w+") as f:
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


    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    #-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # Generate lists of mailings
    # Files are created in reports/APAs
    mailingsCSVFile=Settings().Get("mailings csv file", "mailings.csv")

    with open(os.path.join(rootDir, mailingsCSVFile), 'w', newline="") as csvfile:
        filewriter=csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)

        columnheaders=["IssueName", "Series", "SeriesName", "DisplayName", "DirURL", "PageName", "FIS", "Locale", "PageCount", "Editor", "TagList", "Mailings"]
        filewriter.writerow(columnheaders)

        for issue in fanacIssueList:
            # Select only issues which have an entry in the mailings column
            if len(issue.Mailings) > 0:
                for mailing in issue.Mailings:
                    filewriter.writerow([issue.IssueName, issue.Series, issue.SeriesName, issue.DisplayName, issue.DirURL, issue.PageFilename, issue.FIS, issue.Locale, issue.Pagecount, issue.Editor, issue.Taglist, mailing])


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
    Log("----Begin reading Classic table")
    # This is a list of fanzines on Fanac.org
    # Each item is a tuple of (compressed name,  link name,  link url)
    fanacFanzineDirectoriesList: list[tuple[str, str]]=[]
    directories=ReadList("control-topleveldirectories.txt")
    for dirs in directories:
        ReadModernOrClassicTable(fanacFanzineDirectoriesList, dirs)

    Log("----Done reading Classic table")
    return fanacFanzineDirectoriesList


# ======================================================================
# Read one of the main fanzine directory listings and append all the fanzines directories found to the dictionary
def ReadModernOrClassicTable(fanacFanzineDirectoriesList: list[tuple[str, str]], url: str) -> None:
    h=requests.get(url, headers={'Cache-Control': 'no-cache'})
    s=BeautifulSoup(h.content, "html.parser")
    # We look for the first sortable table that does not contain a "navbar"
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
                    LogError("Bogus row found by ReadModernOrClassicTable")    # There's really nothing to be done except debug...
                    assert()    #TODO: Remove this, as it is temporary
    return


def ReadFile(filename: str) -> list[str]:
    try:
        with open(filename, "r") as f2:
            return f2.readlines()
    except:
        # If the expected control header is unavailable, bail out, otherwise return an empty list.
        LogFailureAndRaiseIfMissing(filename)
    return []

#================================================================================
# fRowHeaderText and fRowBodyText and fSelector are all lambdas
#   fSelector decides if this fanzine is to be listed and returns True for fanzines to be listed, and False for ones to be skipped. (If None, nothing will be skipped)
#   fButtonText operates on an issue and selects the character (or whatever) that will be used for button grouping
#   fRowHeaderText and fRowBodyText are functions which pull information out of a fanzineIssue from fanzineIssueList
#   fRowHeaderText is the item used to decide when to start a new subsection
#   fRowBodyText is what is listed in the subsection
def WriteHTMLTable(filename: str,
               fanacIssueList: list[any],  # The sorted input list
               fURL: Callable[[FanzineIssueInfo], str]|None = None,  # Function to supply the URL
               fDirURL: Callable[[FanzineIssueInfo], str]|None = None,  # Function to supply the directory or root URL
               fButtonText: Callable[[FanzineIssueInfo], str]|None = None,  # Function to supply the button text
                #
               fRowHeaderText: Callable[[FanzineIssueInfo], str]|None = None,  # Function to supply the header text
               fRowHeaderAnnot: Callable[[FanzineIssueInfo], str]|None = None,    # Function to supply annotation to the header text/link
               fRowHeaderSelect: Callable[[FanzineIssueInfo], str]|None = None,  # Function to supply the header text to be used to separate headers. (Needed to disambiguate fanzines series with the same title
               fCompareRowHeaderText: Callable[[str, str], bool]|None = None,  # If present, is used to determine if the row header text has changed
               fHeaderAnnot: Callable[[FanzineIssueInfo], str]|None = None,  # Function to supply annotation to the headers  (unclear this is still needed!)
               includeRowHeaderCounts: bool = True,  # Include counts in header block!
               includeRowTitleCount: bool=False,    # (Only if includeRowHeaderCounts is True,) also include count of series.
               #
               fRowBodyText: Callable[[FanzineIssueInfo], str]|None = None,  # Function to supply the row's body text
               fRowBodyAnnot: Callable[[FanzineIssueInfo], str]|None = None,  # Function to supply annotation to the rows
               fCompareRowBodyText: Callable[[str, str], bool]|None = None,        # If present, is used to determine if the row header text has changed
               fRowBodySelect: Callable[[FanzineIssueInfo], str]|None = None,           # If present, selects the text that is being used to sort body rows
               showDuplicateBodyRows: bool=True,
               #
               topCountText: str= "",
               headerFilename: str="",
               fSelector: Callable[[FanzineIssueInfo], bool]|None = None,            # If present, selects fanzines to be included in report.  Default is to include all.
               inAlphaOrder: bool=False)\
                -> None:

    #Log(f"WriteHTMLTable({filename} called")
    if fCompareRowHeaderText is None:
        fCompareRowHeaderText=lambda f1, f2: f1.casefold() == f2.casefold()
    if fCompareRowBodyText is None:
        fCompareRowBodyText=lambda f1, f2: f1.casefold() == f2.casefold()
    if fRowHeaderText is None:
        LogError(f"WriteTable: critical parameter 'fRowHeaderText' is None in call to generate {filename}")
        return
    if fRowHeaderSelect is None:  # The default is for the header selection rule to be the same as the header; but sometimes this is not the case
        fRowHeaderSelect=fRowHeaderText  # Note that this may also be None
    if fRowBodyText is None:
        LogError(f"WriteTable: critical parameter 'fRowBodyText' is None in call to generate {filename}")
        return
    if fURL is None:
        LogError(f"WriteTable: critical parameter 'fURL' is None in call to generate {filename}")
        return
    if (not showDuplicateBodyRows) and fRowBodySelect is None:
        LogError(f"WriteTable: showDuplicateBodyRows is False, yet fRowBodySelect is None in call to generate {filename}")
        return


    # The file being created.
    with open(filename, "w+") as f:
        #Log(f"WriteHTMLTable({filename} output file opened")

        #--------------------------
        #....... Header .......
        # HTML needs to include a header.
        # It will be a combination of the contents of "control-Header (basic).html" with headerInfoFilename
        basicHeadertext=ReadFile("control-Header (basic).html")
        if not basicHeadertext:
            LogError(f"WriteTable: critical parameter basicHeadertext is None in call to generate {filename}")
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

        # Externally supplied summary count text
        if topCountText:
            topCountText=topCountText.replace("\n", "<p>")
            topCountText=f"<p>{topCountText}</p>\n"
            f.write(topCountText)

        #--------------------------
        # -- Jump buttons --
        # If we have an HTML header, we need to create a set of jump buttons.
        # If it's alpha, the buttons are by 1st letter; if date it's by decade
        # First, we determine the potential button names.  There are two choices: Letters of the alphabet or decades

        headers=set()
        for fz in fanacIssueList:
            if fSelector is not None and not fSelector(fz):
                continue
            if fButtonText is not None:
                if fButtonText(fz) is not None:
                    headers.add(fButtonText(fz))

        headerlist=list(headers)
        headerlist.sort(key=lambda elem: elem.lower())
        buttonlist=""
        for item in headerlist:
            if buttonlist:
                buttonlist=buttonlist+" &mdash; "
            buttonlist+=FormatLink("#"+ item, item)

        # Write out the button bar
        f.write(buttonlist+"<p><p>\n")

        #Log(f"WriteHTMLTable({filename} header complete")

        #--------------------------
        #....... Main table .......
        # Start the table if this is HTML
        # The structure is
        #   <div class="row border">        # This starts a new bordered box (a fanzine, a month)
        #       <div class=col_md_2> (1st col: box title) </div>
        #       <div class=col_md_10> (2nd col, a list of fanzine issues)
        #           <a>issue</a> <br>
        #           <a>issue</a> <br>
        #           <a>issue</a> <br>
        #       </div>
        #   </div>

        f.write('<div>\n')  # Begin the main table

        lastRowHeaderSelect: str=""
        lastRowBodySelect: str=""
        lastButtonLinkString: str=""

        # We walk fanacIssueList by index so we can run a sub-loop for the secondary boxes in the 2nd column.
        for i in range(len(fanacIssueList)):
            fz=fanacIssueList[i]
            #Log(f"WriteHTMLTable({filename} {fz=}")

            # Do we skip this fanzine completely?
            if fSelector is not None and not fSelector(fz):
                continue
            if fURL is not None and fURL(fz) is None:        #TODO: Why do we skip when fURL(fz) is None ??
                continue

            # Start a new main row
            # Deal with Column 1

            # We start a new main row when fCompareRowHeaderText() thinks that fRowHeaderSelect() has changed
            # Note that they have defaults, so they do not need to be checked for None
            if not fCompareRowHeaderText(lastRowHeaderSelect, fRowHeaderSelect(fz)):
                if lastRowHeaderSelect:  # If this is not the first sub-box, we must end the previous sub-box by ending its col 2
                    f.write('    </div></div>\n')

                if includeRowHeaderCounts:
                    # Count the issues in this block.
                    fc=CountSublist(fCompareRowHeaderText, fRowHeaderSelect, fanacIssueList[i:], CountTitles=True)

                # Since this is a new main row, we write the header in col 1
                # Col 1 will contain just one cell while col2 may -- and usually will -- have multiple.

                # Get the button link string, and check if we have a new decade (or 1st letter) and need to create a new jump anchor
                buttonLinkString: str=""
                if fButtonText is not None and fButtonText(fz) is not None:
                    buttonLinkString=fButtonText(fz)
                if buttonLinkString != lastButtonLinkString:
                    f.write('<a name="'+UnicodeToHtml(buttonLinkString)+'"></a>')
                    lastButtonLinkString=buttonLinkString

                f.write('<div class="row border">\n')  # Start a new sub-box
                # Write col 1
                f.write('  <div class=col-md-3>')
                if inAlphaOrder and fDirURL is not None:
                    link=fDirURL(fz)
                    if fz.Series.AlphabetizeIndividually:
                        link+="/"+fz.PageFilename       # When entries are singletons in a collective fanzine index page, we want the col1 link to point to the fanzine, also.
                    f.write(FormatLink(link, UnicodeToHtml(fRowHeaderText(fz))))
                    if fRowHeaderAnnot is not None:
                        f.write(fRowHeaderAnnot(fz))
                elif inAlphaOrder and fDirURL is None:
                    f.write(UnicodeToHtml(fRowHeaderText(fz)))
                    if fRowHeaderAnnot is not None:
                        f.write(fRowHeaderAnnot(fz))
                else:
                    f.write(UnicodeToHtml(fRowHeaderText(fz)))
                if fHeaderAnnot is not None and fHeaderAnnot(fz) is not None:
                    f.write("&nbsp;&nbsp;&nbsp;&nbsp;"+fHeaderAnnot(fz))
                if includeRowHeaderCounts:
                    if includeRowTitleCount:
                        f.write(f"<br><small>{fc}</small>")
                    else:
                        f.write(f"<br><small>{fc}</small>")
                f.write('</div>\n')
                f.write('    <div class=col-md-9>\n') # Start col 2

            #Log(f"WriteHTMLTable({filename} about to check hideSubsequentDuplicateBodyRows ")
            # We sometimes print only the 1st row of column 2 of a block, skipping the rest.
            # These are treated as two separate cases
            # Deal with Column 2
            if showDuplicateBodyRows:
                # The hyperlink goes in column 2, in this case a link to the specific fanzine
                # There are two kinds of hyperlink: Those with just a filename (xyz.html) and those with a full URL (http://xxx.vvv.zzz.html)
                # The former are easy, but the latter need to be processed
                bodytext=fRowBodyText(fz)
                if fURL is not None:
                    # if there is a pipe character in the string, we only link the part before the pipe and delete the pipe
                    splitext=bodytext.split("|", 2)
                    link=fURL(fz)
                    if len(splitext) == 2:
                        f.write('        '+FormatLink(link, splitext[0])+splitext[1])
                    else:
                        f.write('        '+FormatLink(link, bodytext))

                fc=None

                annot=""
                if fRowBodyAnnot is not None:
                    #Log(f"WriteHTMLTable({filename} nAlphaOrder and fRowBodyAnnot is not None")
                    annot=fRowBodyAnnot(fz)
                    if annot is not None:
                        annot=annot.strip()
                if fc is not None:
                    if annot != "":
                        annot+="&nbsp;&nbsp;&nbsp;&nbsp;"
                    annot+=str(fc)
                if annot != "":
                    f.write(Smallify(f"&nbsp;&nbsp;&nbsp;&nbsp;({annot})"))

                f.write('<br>\n')
            else:
                # We're NOT showing duplicate body rows
                # The hyperlink goes in column 2 and is a hyperlink to the *series* since there is only one row for the whole series
                # There are two kinds of hyperlink: Those with just a filename (xyz.html) and those with a full URL (http://xxx.vvv.zzz.html)
                # The former are easy, but the latter need to be processed
                if not fCompareRowBodyText(lastRowBodySelect, fRowBodySelect(fz)):
                    bodytext=fRowBodyText(fz)
                    if fURL is not None:
                        # if there is a pipe character in the string, we only link the part before the pipe and delete the pipe
                        splitext=bodytext.split("|", 2)
                        link=fURL(fz)
                        if fz.Series.AlphabetizeIndividually:
                            link+="/"+fz.PageFilename  # When entries are singletons in a collective fanzine index page, we want the col1 link to point to the fanzine, also.
                        if len(splitext) == 2:
                            f.write('        '+FormatLink(link, splitext[0])+splitext[1])
                        else:
                            f.write('        '+FormatLink(link, bodytext))

                    fc=CountSublist(fCompareRowBodyText, fRowBodySelect, fanacIssueList[i:])

                    annot=""
                    if fRowBodyAnnot is not None:
                        # Log(f"WriteHTMLTable({filename} nAlphaOrder and fRowBodyAnnot is not None")
                        annot=fRowBodyAnnot(fz)
                        if annot is not None:
                            annot=annot.strip()
                    if fc is not None:
                        if annot != "":
                            annot+="&nbsp;&nbsp;&nbsp;&nbsp;"
                        annot+=str(fc)
                    if annot != "":
                        f.write(Smallify(f"&nbsp;&nbsp;&nbsp;&nbsp;({annot})"))

                    f.write('<br>\n')
                    lastRowBodySelect=fRowBodySelect(fz)

            if fRowHeaderSelect is not None:
                lastRowHeaderSelect=fRowHeaderSelect(fz)
        #Log(f"WriteHTMLTable({filename} main loop complete")

        #....... Cleanup .......
        f.write('</div>\n</div>\n')
        f.writelines(ReadFile("control-Default.Footer"))
        Log(f"WriteHTMLTable({filename} completed")



def CountSublist(fCompare: Callable[[str, str], bool], fSelect: Callable[[FanzineIssueInfo], str], fanacIssueList: list[FanzineIssueInfo], CountTitles: bool=False) -> FanzineCounts:
    fc=FanzineCounts()
    tempLastRowHeaderSelect=fSelect(fanacIssueList[0])
    for fztemp in fanacIssueList:  # Loop through fanacIssueList starting at the current position which is the start of a block.
        if not fCompare(tempLastRowHeaderSelect, fSelect(fztemp)):
            break  # Bail when the block selection changes
        fc+=fztemp
        if CountTitles:
            fc+=fztemp.SeriesName
    return fc


#================================================================================
# fRowHeaderText and fRowBodyText and fSelector are all lambdas
#   fSelector decides if this fanzine is to be listed and returns True for fanzines to be listed, and False for ones to be skipped. (If None, nothing will be skipped)
#   fButtonText operates on an issue and selects the character (or whatever) that will be used for button grouping
#   fRowHeaderText and fRowBodyText are functions which pull information out of a fanzineIssue from fanzineIssueList
#   fRowHeaderText is the item used to decide when to start a new subsection
#   fRowBodyText is what is listed in the subsection
def WriteTxtTable(filename: str,
               fanacIssueList: list[any],  # The sorted input list
               fRowBodyText: Callable[[FanzineIssueInfo], str],  # Function to supply the row's body text
               fRowHeaderText: Callable[[FanzineIssueInfo], str]|None = None,  # Function to supply the header text
               fRowHeaderSelect: Callable[[FanzineIssueInfo], str]|None = None,  # Function to supply the header text to be used to separate headers. (Needed to disambiguate fanzines series with the same title
               fHeaderAnnot: Callable[[FanzineIssueInfo], str]|None = None,  # Function to supply annotation to the headers
               fCompareRowHeaderText: Callable[[str, str], bool]|None = None,        # If present, is used to determine if the row header text has changed
               topCountText: str= "",
               fSelector: Callable[[FanzineIssueInfo], bool]|None = None)\
                -> None:
    Log(f"WriteTxtTable({filename} called")
    if fCompareRowHeaderText is None:
        fCompareRowHeaderText=lambda f1, f2: f1 == f2
    if fRowHeaderSelect is None:  # The default is for the header selection rule to be the same as the header; but sometimes this is not the case
        fRowHeaderSelect=fRowHeaderText     # Note that this may also be None

    with open(filename, "w+") as f:

        #....... Header .......
        if topCountText:
            f.write(topCountText)

        lastRowHeaderSelect: str=""
        # We walk fanacIssueList by index so we can run a sub-loop for the secondary boxes in the 2nd column.
        for fz in fanacIssueList:
            # Do we skip this fanzine?
            if fSelector is not None and not fSelector(fz):
                continue

            # Start a new main row?
            # Deal with Column 1
            if fRowHeaderText is not None:
                # We start a new main row when fCompareRowHeaderText() thinks that fRowHeaderSelect() has changed
                # Note that they have defaults, so they do not need to be checked for None
                if not fCompareRowHeaderText(lastRowHeaderSelect, fRowHeaderSelect(fz)):
                    lastRowHeaderSelect=fRowHeaderSelect(fz)

                    f.write("\n"+fRowHeaderText(fz))
                    if fHeaderAnnot is not None and fHeaderAnnot(fz) is not None:
                        f.write("    "+RemoveAllHTMLTags2(fHeaderAnnot(fz)))
                    f.write("\n")

            # Deal with "Column 2" (the indented stuff)
            bodytext=fRowBodyText(fz)
            bodytext=bodytext.replace("|", "", 1)  # Ignore the first  embedded "|" character
            f.write("   "+bodytext+"\n")
    Log(f"WriteTxtTable({filename} completed")



# -------------------------------------------------------------------------
# We have a name and a dirname from the fanac.org Classic and Modern pages.
# The dirname *might* be a URL in which case it needs to be handled as a foreign directory reference
def AddFanacDirectory(fanacFanzineDirectoriesList: list[tuple[str, str]], name: str, dirname: str) -> None:

    # We don't want to add duplicates. A duplicate is one which has the same dirname, even if the text pointing to it is different.
    dups=[e2 for e1, e2 in fanacFanzineDirectoriesList if e2 == dirname]
    if dups:
        Log(f"   AddFanacDirectory: duplicate: {name=}  {dirname=}")
        return

    if dirname.startswith("http"):
        Log(f"    AddFanacDirectory: ignored, because is HTML: {dirname}")
        return

    # Add name and directory reference
    Log(f"   AddFanacDirectory: added to fanacFanzineDirectories:  {name=}  {dirname=}")
    fanacFanzineDirectoriesList.append((name, dirname))
    return


# -------------------------------------------------------------------------
# Compute the button text and URL for an alphabetic fanzine issue -- used in calls to WriteTable
def AlphaButtonText(fz: FanzineIssueInfo) -> str:
    c=FlattenTextForSorting(fz.SeriesName)[0]
    if c == " " or c.isdigit():
        return "*"
    return c.upper()

# -------------------------------------------------------------------------
# Compute a properly formatted date annotation -- used in calls to WriteTable
def AnnotateDate(fz: FanzineIssueInfo) -> str:
    if type(fz) is not FanzineIssueInfo:
        assert ()
    if fz.FIS is None:
        return ""
    if fz.FIS.FD.IsEmpty():
        return ""
    return str(fz.FIS.FD.LongDates).strip()

# -------------------------------------------------------------------------
# Take a string which is lower case and turn it to City, State, US sort of capitalization -- used in calls to WriteTable
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


#----------------------------------------
# Surround the contents by <small>...</small> if it is non-empty
def Smallify(s1: str, s2: str="") -> str:
    if s1 == "":
        return ""
    if s2 == "":
        return f"<small>{s1}</small>"

    return f"<small>{s1}&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{s2}</small>"

#.........................................................
# Compute the button text and links for chronological listings -- used in calls to WriteTable
def ChronButtonText(fz: FanzineIssueInfo) -> str:
    if fz.FIS is None or fz.FIS.Year is None:
        return " "
    return str(fz.FIS.Year)[0:3]+"0s"

#.........................................................
def URL(fz: FanzineIssueInfo) -> str:
    if fz is None or fz.PageFilename == "":
        return "<no url>"
    # Sometimes the url will be to a page in a PDF, so the URL will end with #page=nnn
    # Detect that, since the page needs to be handled specially.
    page=""
    url=fz.DirURL
    m=re.match("(.*)(#page=[0-9]+)$", url)
    if m is not None:
        url=m.groups()[0]
        page=m.groups()[1]

    if "/" not in fz.PageFilename:
        url=url+"/"+fz.PageFilename+page
    else:
        # There are two possibilities: This is a reference to somewhere in the fanzines directory or this is a reference elsewhere.
        # If it is in fanzines, then the url ends with <stuff>/fanzines/<dir>/<file>.html
        parts=fz.PageFilename.split("/")
        if len(parts) > 2 and parts[-3:-2][0] == "fanzines":
            url=url+"/../"+"/".join(parts[-2:])+page
        else:
            url=fz.PageFilename
    return url


# .........................................................
# Compare two strings ignoring punctuation and case -- used in calls to WriteTable
def CompareIgnorePunctAndCase(s1: str, s2: str) -> bool:
    return re.sub("[.,]", "", s1).casefold() == re.sub("[.,]", "", s2).casefold()


# .........................................................
# Truncate a string on the first digits found -- used in calls to WriteTable
def TruncOnDigit(s: str) -> str:
    m=re.match("([^0-9]*?)[0-9]", s)
    if m is not None:
        return m.groups()[0]
    return s


#######################################
#######################################
# Run main()
if __name__ == "__main__":
    main()