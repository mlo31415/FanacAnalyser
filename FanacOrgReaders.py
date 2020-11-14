from typing import Union, Tuple, Optional, List, Dict
from contextlib import suppress
from bs4 import BeautifulSoup
from bs4 import NavigableString
from bs4 import Tag
import requests
import re
import urllib.parse
import os


from FanzineIssueSpecPackage import FanzineIssueSpec, FanzineDate, FanzineSerial, FanzineIssueInfo
from FanzineIssueSpecPackage import ExtractSerialNumber

from Log import Log, LogSetHeader
from HelpersPackage import ReadList, FindBracketedText
from HelpersPackage import RelPathToURL, ChangeFileInURL, ChangeNBSPToSpace, RemoveAllHTMLTags2
from HelpersPackage import CanonicizeColumnHeaders
from HelpersPackage import IsInt

# ============================================================================================
def ReadFanacFanzineIssues(fanacDirectories: List[Tuple[str, str]]) -> Tuple[List[FanzineIssueInfo], List[str]]:
    # Read index.html files on fanac.org
    # We do this by reading the fanzines/<name>/index.html file and then decoding the table in it.
    # What we get out of this is a list of fanzines with name, URL, and issue info.
    # Loop over the list of all fanzines, building up a list of those on fanac.org
    Log("----Begin reading index.html files on fanac.org")

    global g_browser
    g_browser=None
    fanacIssueInfo=[]
    newszineList=[]

    fanacDirectories.sort(key=lambda tup: tup[1])
    for title, dirname in fanacDirectories:
        # This bit allows us to skip all *but* the fanzines in unskippers. It's for debugging purposes only
        unskippers=[
            #"MT_Void",
            #"Coventranian_Gazette",
            #"Syndrome",
            #"Booklist",
            #"Axe",
            #"Opuntia",
            #"Irish_Fandom",
            #"StraightUp",
            #"Vega",
            #"Fantasy_News",
            #"FuturiaFantasia",
            #"Le_Zombie",
            #"Spaceways",
            #"MelbourneBulletin",
            #"Sanders",
            #"Speculation",
            #"SFSFS",
            #"SkyHook",
            #"Fantasy_News",
            #"Scienti-Snaps",
            #"A_Bas",
            #"Bay_Area_News",
            #"Degler",
            #"BrokenToys",
            #"Aspidistra"
        ]
        if len(unskippers) > 0 and dirname not in unskippers:  continue     # If and only if there are unskippers present, skip everything else

        LogSetHeader("'"+dirname+"'      '"+title+"'")

        global skippers  # Not actually used anywhere else, but for performance sake, should be read once and retained
        try:
            skippers
        except NameError:
            skippers=ReadList("control-skippers.txt")
        if dirname in skippers:
            Log("...Skipping because it is in skippers: "+dirname, isError=True)
            continue

        # Some fanzines are listed in our tables, but are offsite and do not even have an index table on fanac.org
        global offsite  # Not actually used anywhere else, but for performance sake, should be read once and retained
        try:
            offsite
        except NameError:
            offsite=ReadList("control-offsite.txt")
        if dirname in offsite:
            Log("...Skipping because it is in offsite: "+dirname)
            continue

        # Besides the offsite table, we try to detect references which are offsite from their URLs
        if dirname.startswith("http://"):
            Log("...Skipped because the index page pointed to is not on fanac.org: "+dirname, isError=True)
            continue

        # The URL we get is relative to the fanzines directory which has the URL fanac.org/fanzines
        # We need to turn relPath into a URL
        url=RelPathToURL(dirname)
        if url is None:
            continue
        if not url.startswith("http://www.fanac.org"):
            Log("...Skipped because not a fanac.org url: "+url, isError=True)
            continue

        # if url.startswith("http://www.fanac.org//fan_funds") or url.startswith("http://www.fanac.org/fanzines/Miscellaneous"):
        #     Log("***skipped because in the fan_funds or fanzines/Miscellaneous directories: "+url, isError=True)
        #     continue

        ReadAndAppendFanacFanzineIndexPage(title, url, fanacIssueInfo, newszineList)

    # Now fanacIssueList is a list of all the issues of fanzines on fanac.org
    Log("----Done reading index.html files on fanac.org")
    if g_browser is not None:
        g_browser.quit()

    fanacIssueInfo=RemoveDuplicates(fanacIssueInfo)

    return fanacIssueInfo, newszineList


#=============================================================================================
# Remove the duplicates from a fanzine list
def RemoveDuplicates(fanzineList: List[FanzineIssueInfo]) -> List[FanzineIssueInfo]:
    # Sort in place on fanzine's Directory's URL followed by file name
    fanzineList.sort(key=lambda fz: fz.PageName if fz.PageName is not None else "")
    fanzineList.sort(key=lambda fz: fz.DirURL if fz.DirURL is not None else "")

#TODO Drop external links which duplicate Fanac.org
    # Any duplicates will be adjacent, so search for adjacent directoryURL+URL
    last=""
    dedupedList=[]
    for fz in fanzineList:
        this=fz.DirURL+(fz.PageName if fz.PageName is not None else "")
        if this != last:
            dedupedList.append(fz)
        last=this
    return dedupedList


#=============================================================================================
# Given a list of column headers and a list of row cell values, return the cell matching the header
# If cellname is a list of names, try them all and return the first that hits
def GetCellValueByColHeader(columnHeaders: list, row: List[str], cellnames: Union[str, List[str]]) -> Optional[str]:

    if type(cellnames) is list:
        for i in range(0, len(columnHeaders)):
            for cn in cellnames:
                if CanonicizeColumnHeaders(columnHeaders[i]) == CanonicizeColumnHeaders(cn):
                    return ChangeNBSPToSpace(row[i])
    else:
        for i in range(0, len(columnHeaders)):
            if CanonicizeColumnHeaders(columnHeaders[i]) == CanonicizeColumnHeaders(cellnames):
                return ChangeNBSPToSpace(row[i])

    return None


#=============================================================================================
# Extract a date from a table row
# We return a tuple: (yearInt, yearText, monthInt, monthText, dayInt, dayText)
def ExtractDate(columnHeaders: List[str], row: List[str]) -> FanzineDate:

    # Does this have a Date column?  If so, that's all we need. (I hope...)
    dateText=GetCellValueByColHeader(columnHeaders, row, "Date")
    if dateText is not None and len(dateText) > 0:
        # Get the date
        with suppress(Exception):
            return FanzineDate().Match(dateText)

    # Next, take the various parts and assemble them and try to interpret the result using the FanzineDate() parser
    yearText=GetCellValueByColHeader(columnHeaders, row, "Year")
    monthText=GetCellValueByColHeader(columnHeaders, row, "Month")
    dayText=GetCellValueByColHeader(columnHeaders, row, "Day")

    if yearText is not None:
        if monthText is not None:
            if dayText is not None:
                constructedDate=monthText+" "+dayText+", "+yearText
            else:
                constructedDate=monthText+" "+yearText
        else:
            if dayText is not None:
                constructedDate=dayText+" "+yearText
            else:
                constructedDate=yearText
        Log("   constructed date='"+constructedDate+"'")
        if constructedDate is not None:
            fd=FanzineDate().Match(constructedDate)
            if not fd.IsEmpty():
                return fd

    # Well, that didn't work.
    if yearText is None or not IsInt(yearText):
        Log("   ***Date conversion failed: no useable date columns data found")

    # Try to build up a FanzineDate "by hand", so to speak
    fd=FanzineDate(Year=yearText, MonthText=monthText)
    Log("By hand: "+str(fd))
    return fd


#=============================================================================================
# Extract a serial number (vol, num, whole_num) from a table row
# We return a tuple: (vol, num)
# Some fanzines have a whole number --> returned as VolNone, Num=nnn
# Others have a Volume and a number --> returned as Vol=nn, Num=nn
# Sometimes the number is composite V2#3 and stored who-knows-where and we gotta find it.
def ExtractSerial(columnHeaders: List[str], row: List[str]) -> FanzineSerial:

    wholeText=GetCellValueByColHeader(columnHeaders, row, "Whole")
    volText=GetCellValueByColHeader(columnHeaders, row, "Volume")
    numText=GetCellValueByColHeader(columnHeaders, row, "Number")
    volNumText=GetCellValueByColHeader(columnHeaders, row, "VolNum")
    if type(volNumText) is tuple:
        volNumText=volNumText[0]

    titleText=GetCellValueByColHeader(columnHeaders, row, ["Title", "Issue"])

    return ExtractSerialNumber(volText, numText, wholeText, volNumText, titleText)


#============================================================================================
# Find the cell containing the page count and return its value
def ExtractPageCount(columnHeaders: List[str], row: List[str]) -> int:

    pageText=GetCellValueByColHeader(columnHeaders, row, ["Pages", "Pp.", "Page"])
    if pageText is None:
        # If there's no column labelled for page count, check to see if there's a "Type" column with value "CARD".
        # These are newscards and are by definition a single page.
        pageText=GetCellValueByColHeader(columnHeaders, row, "Type")
        if pageText is not None and pageText.lower() == "card":
            return 1    # All cards have a pagecount of 1
        return 0

    with suppress(Exception):
        return int(pageText)

    return 0


# ============================================================================================
# Find the cell containing the issue name
def FindIssueCell(columnHeaders: List[str], row: List[str]) -> str:
    # Now find the column containing the issue designation. It could be "Issue" or "Title"
    issueCell=GetCellValueByColHeader(columnHeaders, row, "Issue")
    if issueCell is None:
        issueCell=GetCellValueByColHeader(columnHeaders, row, "Title")
    if issueCell is None:
        issueCell="<not found>"

    return issueCell


# ============================================================================================
# Scan the row and locate the issue cell, title and href and return them as a tuple
def ExtractHrefAndTitle(columnHeaders: List[str], row: List[str]) -> Tuple[Optional[str], Optional[str]]:

    issueCell=FindIssueCell(columnHeaders, row)

    # If necessary, separate the href and the name
    if type(issueCell) is list:
        return issueCell[0], issueCell[1]
    name=issueCell      # issueCell is just the name

    if name is None:
        return None, None

    # Sometimes the title of the fanzine is in one column and the hyperlink to the issue in another.
    # If we don't find a hyperlink in the title, scan the other cells of the row for the first col containing a hyperlink
    for i in range(0, len(columnHeaders)):
        if type(row[i]) is tuple:
            n, h=row[i]
            if h is not None:
                href=h
                return name, href

    return name, None


# ============================================================================================
def ExtractCountry(soup: BeautifulSoup) -> str:
    country=""
    temp=FindBracketedText(str(soup.body), "fanac-type")
    if temp[0] is not None and len(temp[0]) > 0:
        temp=RemoveAllHTMLTags2(temp[0])
        loc=temp.find(":")
        if loc > 0 and loc+1 < len(temp):
            country=temp[loc+1:].strip()
    return country


# ============================================================================================
# Function to extract information from a fanac.org fanzine index.html page
def ReadAndAppendFanacFanzineIndexPage(fanzineName: str, directoryUrl: str, fanzineIssueList: List[FanzineIssueInfo], newszineList: List[str]) -> None:
    global g_browser

    Log("ReadAndAppendFanacFanzineIndexPage: "+fanzineName+"   "+directoryUrl)

    # Fanzines with only a single page rather than an index.
    # Note that these are directory names
    global singletons   # Not actually used anywhere else, but for performance sake, should be read once and retained
    try:
        singletons
    except NameError:
        singletons=ReadList("control-singletons.txt")

    # We have some pages where we have a tree of pages with specially-flagged fanzine index tables at the leaf nodes.
    # If this is the root of one of them...
    global specialBiggies   # Not actually used anywhere else, but for performance sake, should be read once and retained
    try:
        specialBiggies
    except NameError:
        specialBiggies=ReadList("control-specialBiggies.txt")

    if fanzineName in specialBiggies:
        ReadSpecialBiggie(directoryUrl, fanzineIssueList, fanzineName)
        return

    # It looks like this is a single level directory.
    soup=OpenSoup(directoryUrl)
    if soup is None:
        return

    # We need to handle singletons specially
    if directoryUrl.endswith(".html") or directoryUrl.endswith(".htm") or directoryUrl.split("/")[-1:][0] in singletons:
        ReadSingleton(directoryUrl, fanzineIssueList, fanzineName, soup)
        return

    # By elimination, this must be an ordinary page, so read it.
    # Locate the Index Table on this page.
    table=LocateIndexTable(directoryUrl, soup)
    if table is None:
        return

    # Check to see if this is marked as a Newszine
    temp=soup.h2
    if temp.text.find("Newszine") > -1:
        Log(">>>>>> Newszine added: '"+fanzineName+"'")
        newszineList.append(fanzineName)

    country=ExtractCountry(soup)

    # Walk the table and extract the fanzines in it
    ExtractFanzineIndexTableInfo(directoryUrl, fanzineIssueList, fanzineName, table, country)
    return


#===================================================================================
# The "special biggie" pages are few (only two at the time this ie being written) and need to be handled specially
# The characteristic is that they are a tree of pages which may contain one or more *tagged* fanzine index tables on any level.
# The strategy is to first look for pages at this level, then recursively do the same for any links to a lower level page (same directory)
def ReadSpecialBiggie(directoryUrl: str, fanzineIssueList: List[FanzineIssueInfo], fanzineName: str) -> None:

    soup=OpenSoup(directoryUrl)
    if soup is None:
        return

    # Look for and interpret all flagged tables on this page, and look for links to subdirectories.

    # Scan for flagged tables on this page
    table=LocateIndexTable(directoryUrl, soup, silence=True)
    country=ExtractCountry(soup)
    if table is not None:
        ExtractFanzineIndexTableInfo(directoryUrl, fanzineIssueList, fanzineName, table, country)

    # Now look for hyperlinks deeper into the directory. (Hyperlinks going outside the directory are not interesting.)
    links=soup.find_all("a")
    for link in links:
        # If it's an html file it's probably worth investigating
        if "href" in link.attrs.keys():     # Some pages have <A NAME="1"> tags which we need to ignore
            url=link.attrs["href"]
            p=re.compile("^[a-zA-Z0-9\-_]*.html$")
            m=p.match(url)
            if m is not None:
                if url.startswith("index") or url.startswith("archive") or url.startswith("Bullsheet1-00") or url.startswith("Bullsheet2-00"):
                    u=ChangeFileInURL(directoryUrl, url)
                    ReadSpecialBiggie(u, fanzineIssueList, fanzineName)
    return


#======================================================================================
# Open a directory's index webpage using BeautifulSoup
def OpenSoup(directoryUrl: str) -> Optional[BeautifulSoup]:
    # Download the index.html, which is
    # * The fanzine's Issue Index Table page
    # * A singleton page
    # * The root of a tree with multiple Issue Index Pages
    Log("    opening "+directoryUrl, noNewLine=True)
    try:
        h=requests.get(directoryUrl, timeout=1)
    except:
        try:    # Do first retry
            h=requests.get(directoryUrl, timeout=2)
        except:
            try:  # Do second retry
                h=requests.get(directoryUrl, timeout=2)
            except:
                Log("\n***OpenSoup failed because it didn't load: "+directoryUrl, isError=True)
                return None
    Log("...loaded", noNewLine=True)

    # Next, parse the page looking for the body
    soup=BeautifulSoup(h.content, "lxml")   # "html.parser"
    Log("...BeautifulSoup opened")
    return soup


#=====================================================================================
# Function to pull an href and the accompanying text from a Tag
# The structure is "<a href='URL'>LINKTEXT</a>
# We want to extract the URL and LINKTEXT
def GetHrefAndTextFromTag(tag: Tag) -> Tuple[str, Optional[str]]:
    try:
        href=tag.contents[0].attrs.get("href", None)
    except:
        try:
            href=tag.attrs.get("href")
        except:
            return "Failed href in GetHrefAndTextFromTag()", None

    return tag.contents[0].string, href


#======================================================================================
# Read a singleton-format fanzine page
def ReadSingleton(directoryUrl: str, fanzineIssueList: List[FanzineIssueInfo], fanzineName: str, soup) -> None:
    # Usually, a singleton has the information in the first h2 block
    if soup.h2 is None:
        Log("***Failed to find <h2> block in singleton '"+directoryUrl+"'", isError=True)
        return

    content=[str(e) for e in soup.h2.contents if type(e) is NavigableString]

    # The title is the first line
    title=content[0]

    # The date is the first line that looks like a date
    date=None
    for c in content:
        date=FanzineDate().Match(c)
        if not date.IsEmpty():
            break
    if date.IsEmpty():
        Log("***Failed to find date in <h2> block in singleton '"+directoryUrl+"'", isError=True)
        return
    fis=FanzineIssueSpec(FD=date)
    fii=FanzineIssueInfo(SeriesName=fanzineName, IssueName=content[0], DirURL=directoryUrl, PageName="", FIS=fis, Pagecount=0)
    Log("   (singleton): "+str(fii))
    fanzineIssueList.append(fii)
    return


#=====================================================================================
# Function to compress newline elements from a list of Tags.
def RemoveNewlineRows(tags: List[Tag]) -> List[Tag]:
    compressedTags = []
    for row in tags:
        if not isinstance(row, NavigableString):
            compressedTags.append(row)
    return compressedTags


#=========================================================================================
# Read a fanzine's page of any format
def ExtractFanzineIndexTableInfo(directoryUrl: str, fanzineIssueList: List[FanzineIssueInfo], fanzineName: str, table: Tag, country: str) -> None:

    # OK, we probably have the issue table.  Now decode it.
    # The first row is the column headers
    # Subsequent rows are fanzine issue rows
    Log(directoryUrl+"\n")

    # Start by creating a list of the column headers.  This will be used to locate information in each row.
    columnHeaders=[]

    # Create a composition of all columns. The header column may have newline eleemnts, so compress them out.
    # Then compress out sizes in the actual column header, make them into a list, and then join the list separated by spaces
    table.contents=[t for t in table.contents if not isinstance(t, NavigableString)]
    if len(table.contents[0])>1:
        columnHeaders=table.contents[0].text.strip()
    columnHeaders=columnHeaders.split("\n")
    columnHeaders=[CanonicizeColumnHeaders(c) for c in columnHeaders]

    # We need to pull the fanzine rows in from BeautifulSoup and save them in the same format for later analysis.
    # The format will be a list of rows
    # Each row will be a list of cells
    # Each cell will be either a text string or, if the cell contained a hyperlink, a tuple containing the cell text and the hyperlink
    tableRows=[]
    for i in range(1, len(table)):
        tableRow=RemoveNewlineRows(table.contents[i])
        newRow=[]
        for cell in tableRow:
            cellval=GetHrefAndTextFromTag(cell)
            if cellval[1] is None:
                newRow.append(cellval[0])
            else:
                newRow.append(cellval)
        tableRows.append(newRow)

#TODO: We need to skip entries which point to a directory: E.g., Axe in Irish_Fandom
    # Now we process the table rows, extracting the information for each fanzine issue.
    for iRow in range(len(tableRows)):
        # We need to skip the column headers
        tableRow=tableRows[iRow]
        if len(tableRow)==1 and tableRow[0]=="\n":  # Skip empty rows
            continue
        Log("   row="+str(tableRow))

        # We need to extract the name, url, year, and vol/issue info for each fanzine
        # We have to treat the Title column specially, since it contains the critical href we need.
        date=ExtractDate(columnHeaders, tableRow)
        ser=ExtractSerial(columnHeaders, tableRow)
        fis=FanzineIssueSpec(FD=date, FS=ser)
        name, href=ExtractHrefAndTitle(columnHeaders, tableRow)
        pages=ExtractPageCount(columnHeaders, tableRow)

        # Sometimes we have a reference in one directory be to a fanzine in another. (Sometimes these are duplicate, but this will be taken care of elsewhere.)
        # If the href is a complete fanac.org URL and not relative (i.e, 'http://www.fanac.org/fanzines/FAPA-Misc/FAPA-Misc24-01.html' and not 'FAPA-Misc24-01.html'),
        # we need to check to see if it has directoryURL as a prefix (in which case we delete the prefix) or it has a *different* fanac.org URL, in which case we
        # change the value of directoryURL for this fanzine.
        dirUrl=directoryUrl
        if href is not None:
            if href.startswith(directoryUrl):
                href=href.replace(directoryUrl, "")
                if href[0] == "/":
                    href=href[1:]   # Delete any remnant leading "/"
            elif href.startswith("http://www.fanac.org/") or href.startswith("http://fanac.org/"):
                # OK, this is a fanac URL.  Divide it into a file and a path
                fname=urllib.parse.urlparse(href).path.split("/")[-1:][0]
                if len(fname) == 0:
                    Log("***FanacOrgReaders: href='"+href+"' seems to be pointing to a directory, not a file. Skipped", isError=True)
                    continue
                path=href.replace("/"+fname, "")
                href=fname
                dirUrl=path

        # In cases where there's a two-level index, the dirurl is actually the URL of an html file.
        # We need to remove that filename before using it to form other URLs
        u=urllib.parse.urlparse(dirUrl)     # u is an annoying 6-tuple which needs to be modified and then reassembled
        h, t=os.path.split(u[2])
        if t.lower().endswith("htm") or t.lower().endswith(".html"):    # If the last part of the URL is a filename (ending in html) then we remove it since we only want the dirname
            t=""
        dirUrl=urllib.parse.urlunparse((u[0], u[1], os.path.join(h, t), u[3], u[4], u[5]))

        # And save the results
        fi=FanzineIssueInfo(SeriesName=fanzineName, IssueName=name, DirURL=dirUrl, PageName=href, FIS=fis, Pagecount=pages, Country=country)
        if fi.IssueName == "<not found>" and fi.FIS.Vol is None and fi.FIS.Year is None and fi.FIS.Month is None:
            Log("   ****Skipping null table row: "+str(fi))
            continue

        Log("   "+str(fi))
        fanzineIssueList.append(fi)

        # Log it.
        if fi is not None:
            urlT=""
            if fi.PageName is None:
                urlT="*No PageName*"
            Log("Row "+str(iRow)+"  '"+str(fi.IssueName)+"'  ["+str(fi.FIS)+"]  "+urlT)
        else:
            Log(fanzineName+"      ***Can't handle "+dirUrl, isError=True)


#=====================================================================================
# Function to search recursively for the table containing the fanzines listing
# flags is a dictionary of attributes and values to be matched, e.g., {"class" : "indextable", ...}
# We must match all of them
def LookForTable(soup: BeautifulSoup, flags: Dict[str, str]) -> Optional[Tag]:

    tables=soup.find_all("table")
    for table in tables:
        ok=True
        for key in flags.keys():
            if key not in table.attrs or table.attrs[key] is None or table.attrs[key] != flags[key]:
                ok=False
                break
        if ok:
            return table
    return None


#===============================================================================
# Locate a fanzine index table.
def LocateIndexTable(directoryUrl: str, soup: BeautifulSoup, silence: bool=False) -> Optional[Tag]:
    global g_browser

    # Because the structures of the pages are so random, we need to search the body for the table.
    # *So far* nearly all of the tables have been headed by <table border="1" cellpadding="5">, so we look for that.
    table=LookForTable(soup, {"border" : "1", "cellpadding" : "5"})
    if table is not None:
        return table

    # A few cases have been tagged explicitly
    table=LookForTable(soup, {"class" : "indextable"})
    if table is not None:
        return table

    # Then there's Peon...
    table=LookForTable(soup, {"border" : "1", "cellpadding" : "3"})
    if table is not None:
        return table

    # Then there's Bable-On...
    table=LookForTable(soup, {"cellpadding" : "10"})
    if table is not None:
        return table

    if not silence:
        Log("***failed because BeautifulSoup found no index table in index.html: "+directoryUrl, isError=True)
    return None
