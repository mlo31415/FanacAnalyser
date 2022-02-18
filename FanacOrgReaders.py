from typing import Union, Optional
from contextlib import suppress
import os
import re
from difflib import SequenceMatcher
from bs4 import BeautifulSoup, NavigableString, Tag
import requests
import urllib.parse


from FanzineIssueSpecPackage import FanzineIssueSpec, FanzineDate, FanzineSerial, FanzineIssueInfo, FanzineSeriesInfo
from FanzineIssueSpecPackage import ExtractSerialNumber
from Locale import Locale

from Log import Log, LogSetHeader
from HelpersPackage import ReadList, FindBracketedText
from HelpersPackage import RelPathToURL, ChangeFileInURL, ChangeNBSPToSpace
from HelpersPackage import CanonicizeColumnHeaders
from HelpersPackage import IsInt, Int0

# ============================================================================================
def ReadFanacFanzineIssues(fanacDirectories: list[tuple[str, str]]) -> list[FanzineIssueInfo]:
    # Read index.html files on fanac.org
    # We do this by reading the fanzines/<name>/index.html file and then decoding the table in it.
    # What we get out of this is a list of fanzines with name, URL, and issue info.
    # Loop over the list of all fanzines, building up a list of those on fanac.org
    Log("----Begin reading index.html files on fanac.org")

    fanacIssueInfo: list[FanzineIssueInfo]=[]

    fanacDirectories.sort(key=lambda tup: tup[1])
    for title, dirname in fanacDirectories:
        # This bit allows us to skip all *but* the fanzines in unskippers. It's for debugging purposes only
        unskippers=[
            #"MT_Void",
            #"Coventranian_Gazette",
            #"Solstice",
            #"Syndrome",
            #"Booklist",
            #"Axe",
            #"Opuntia",
            #"Inside",
            #"Irish_Fandom",
            # "StraightUp",
            # "Trumpet",
            # "Tumbrils",
            # "Vanations",
            # "Viewpoints",
            #"Riverside_Quarterly",
            #"Texas-SF-Inquirer",
            #"Mimosa",
            #"Vega",
            #="Classifications",
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
            #"Aspidistra",
            #"FAPA_Mailings",
            #"Zed",
            #"Musicals",
            #"Fantasy_Fiction_Field"
        ]
        if len(unskippers) > 0 and dirname not in unskippers:  continue     # If and only if there are unskippers present, skip everything else

        LogSetHeader("'"+dirname+"'      '"+title+"'")

        global skippers  # Not actually used anywhere else, but for performance sake, should be read once and retained
        try:
            skippers
        except NameError:
            skippers=ReadList("control-skippers.txt")
            #skippers.append("ScienceFictionFan")
        if dirname in skippers:
            Log(f"...Skipping because it is in skippers: {dirname}", isError=True)
            continue

        # Some fanzines are listed in our tables, but are offsite and do not even have an index table on fanac.org
        global offsite  # Not actually used anywhere else, but for performance sake, should be read once and retained
        try:
            offsite
        except NameError:
            offsite=ReadList("control-offsite.txt")
        if dirname in offsite:
            Log(f"...Skipping because it is in offsite: {dirname}")
            continue

        # Besides the offsite table, we try to detect references which are offsite from their URLs
        if dirname.startswith("http://"):
            Log(f"...Skipped because the index page pointed to is not on fanac.org: {dirname}", isError=True)
            continue

        # The URL we get is relative to the fanzines directory which has the URL fanac.org/fanzines
        # We need to turn relPath into a URL
        url=RelPathToURL(dirname)
        if url is None:
            continue
        if not url.startswith("https://www.fanac.org"):
            Log(f"...Skipped because not a fanac.org url: {url}", isError=True)
            continue

        # if url.startswith("http://www.fanac.org//fan_funds") or url.startswith("http://www.fanac.org/fanzines/Miscellaneous"):
        #     Log("***skipped because in the fan_funds or fanzines/Miscellaneous directories: "+url, isError=True)
        #     continue

        fanacIssueInfo.extend(ReadAndAppendFanacFanzineIndexPage(title, url))

    # Now fanacIssueList is a list of all the issues of fanzines on fanac.org
    Log("----Done reading index.html files on fanac.org")

    fanacIssueInfo=RemoveDuplicates(fanacIssueInfo)

    return fanacIssueInfo


#=============================================================================================
# Remove the duplicates from a fanzine list
def RemoveDuplicates(fanzineList: list[FanzineIssueInfo]) -> list[FanzineIssueInfo]:
    # Sort in place on fanzine's Directory's URL followed by file name
    fanzineList.sort(key=lambda fz: fz.PageName if fz.PageName is not None else "")
    fanzineList.sort(key=lambda fz: fz.DirURL if fz.DirURL is not None else "")

#TODO Drop external links which duplicate Fanac.org
    # Any duplicates will be adjacent, so search for adjacent directoryURL+URL
    last=""
    dedupedList: list[FanzineIssueInfo]=[]
    for fz in fanzineList:
        this=fz.DirURL+(fz.PageName if fz.PageName is not None else "")
        if this != last:
            dedupedList.append(fz)
        last=this
    return dedupedList


#=============================================================================================
# Given a list of column headers and a list of row cell values, return the cell matching the header
# If cellname is a list of names, try them all and return the first that hits
def GetCellValueByColHeader(columnHeaders: list, row: list[tuple[str, str]], cellnames: Union[str, list[str]]) -> tuple[str, str]:

    # Make sure we have a list of cell names
    celllist=cellnames if type(cellnames) is list else [cellnames]
    for cn in celllist:
        for i, header in enumerate(columnHeaders):
            if CanonicizeColumnHeaders(header) == CanonicizeColumnHeaders(cn):
                return ChangeNBSPToSpace(row[i][0]), row[i][1]

    return "", ""


#=============================================================================================
# Extract a date from a table row
# We return a tuple: (yearInt, yearText, monthInt, monthText, dayInt, dayText)
def ExtractDate(columnHeaders: list[str], row: list[tuple[str, str]]) -> FanzineDate:

    # Does this have a Date column?  If so, that's all we need. (I hope...)
    dateText=GetCellValueByColHeader(columnHeaders, row, "Date")[0]
    if dateText is not None and len(dateText) > 0:
        # Get the date
        with suppress(Exception):
            return FanzineDate().Match(dateText)

    # Next, take the various parts and assemble them and try to interpret the result using the FanzineDate() parser
    yearText=GetCellValueByColHeader(columnHeaders, row, "Year")[0]
    monthText=GetCellValueByColHeader(columnHeaders, row, "Month")[0]
    dayText=GetCellValueByColHeader(columnHeaders, row, "Day")[0]

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
        Log(f"   constructed date='{constructedDate}'")
        if constructedDate is not None:
            fd=FanzineDate().Match(constructedDate)
            if not fd.IsEmpty():
                return fd

    # Well, that didn't work.
    if yearText is None or not IsInt(yearText):
        Log("   ***Date conversion failed: no useable date columns data found")

    # Try to build up a FanzineDate "by hand", so to speak
    fd=FanzineDate(Year=yearText, MonthText=monthText)
    Log(f"By hand: {fd}")
    return fd


#=============================================================================================
# Extract a serial number (vol, num, whole_num) from a table row
# We return a tuple: (vol, num)
# Some fanzines have a whole number --> returned as VolNone, Num=nnn
# Others have a Volume and a number --> returned as Vol=nn, Num=nn
# Sometimes the number is composite V2#3 and stored who-knows-where and we gotta find it.
def ExtractSerial(columnHeaders: list[str], row: list[tuple[str, str]]) -> FanzineSerial:

    wholeText=GetCellValueByColHeader(columnHeaders, row, "Whole")[0]
    volText=GetCellValueByColHeader(columnHeaders, row, "Volume")[0]
    numText=GetCellValueByColHeader(columnHeaders, row, "Number")[0]
    volNumText=GetCellValueByColHeader(columnHeaders, row, "VolNum")[0]
    if type(volNumText) is tuple:
        volNumText=volNumText[0]

    titleText=GetCellValueByColHeader(columnHeaders, row, ["Title", "Issue"])[0]

    return ExtractSerialNumber(volText, numText, wholeText, volNumText, titleText)


#============================================================================================
# Find the cell containing the page count and return its value
def ExtractPageCount(columnHeaders: list[str], row: list[tuple[str, str]]) -> int:

    pageText=GetCellValueByColHeader(columnHeaders, row, ["Pages", "Pp.", "Page"])[0]
    if pageText is None:
        # If there's no column labelled for page count, check to see if there's a "Type" column with value "CARD".
        # These are newscards and are by definition a single page.
        pageText=GetCellValueByColHeader(columnHeaders, row, "Type")[0]
        if pageText is not None and pageText.lower() == "card":
            return 1    # All cards have a pagecount of 1
        return 0

    return Int0(pageText)


#============================================================================================
# Find the cell containing the page count and return its value
def ExtractMailings(columnHeaders: list[str], row: list[tuple[str, str]]) -> list[str]:

    mailingText=GetCellValueByColHeader(columnHeaders, row, ["Mailing"])[0]
    if mailingText is None or len(mailingText) == 0:
        return []
    # The mailing text is a series of APA names followed by alphanumerics separated by semicolons
    pattern="([a-zA-Z0-9\-]\w+[[a-zA-Z0-9\-])[,;]\w*"

    mailingslist=[]
    mailingText=mailingText.strip()

    def subber(m) -> str:
        mailingslist.append(m.groups(0))
        return ""

    mailingtext=re.sub(pattern, subber, mailingText)
    if mailingtext:
        mailingslist.append(mailingtext)

    return mailingslist

# ============================================================================================
# Find the cell containing the issue name
def FindIssueCell(columnHeaders: list[str], row: list[tuple[str, str]]) -> tuple[str, str]:
    # Now find the column containing the issue designation. It could be "Issue" or "Title"
    issueCell=GetCellValueByColHeader(columnHeaders, row, "Issue")
    if issueCell == ("", ""):
        issueCell=GetCellValueByColHeader(columnHeaders, row, "Title")
    if issueCell == ("", ""):
        issueCell="<not found>", ''

    return issueCell


# ============================================================================================
# Scan the row and locate the issue cell, title and href and return them as a tuple
def ExtractHrefAndTitle(columnHeaders: list[str], row: list[tuple[str, str]]) -> tuple[str, str]:

    issueCell=FindIssueCell(columnHeaders, row)

    # If necessary, separate the href and the name
    if issueCell[1] != "":
        return issueCell
    name=issueCell[0]      # issueCell is just the name

    if name is None:
        return "", ""

    # Sometimes the title of the fanzine is in one column and the hyperlink to the issue in another.
    # If we don't find a hyperlink in the title, scan the other cells of the row for the first col containing a hyperlink
    # We return the name from the issue cell and the hyperlink from the other cell
    for i in range(0, len(columnHeaders)):
        if row[i][1] != "":
            return name, row[i][1]

    return name, ""     # No hyperlink found


# ============================================================================================
def ExtractCountry(h: str) -> str:
    temp=FindBracketedText(h, "fanac-type")
    if temp[0] is None or len(temp[0]) == 0:
        return ""

    loc=Locale(temp[0])
    Log(f'ExtractCountry: "{temp[0]}" --> {loc}')
    return loc.Country

    # # There are two formats for this text:
    # #       Country: <country>
    # #       <country>:<city>, <state>
    # temp=RemoveAllHTMLTags2(temp[0])
    #
    # # Look for "Country: <country>
    # m=re.search("\s*Country:\s*([a-zA-Z ]+)", temp)
    # if m is not None:
    #     return m.groups()[0]
    #
    # # Look for <country>:<state/city>
    # m=re.search("\s*([a-zA-Z. ]+):([a-zA-Z. ]*)[,]?\s*([a-zA-Z. ]?)", temp)
    # if m is not None:
    #     return m.groups()[0]
    #
    # return ""

# ============================================================================================
# Function to extract information from a fanac.org fanzine index.html page
def ReadAndAppendFanacFanzineIndexPage(fanzineName: str, directoryUrl: str) -> list[FanzineIssueInfo]:

    Log(f"ReadAndAppendFanacFanzineIndexPage: {fanzineName}   {directoryUrl}")

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
        return ReadSpecialBiggie(directoryUrl,fanzineName)

    # It looks like this is a single level directory.
    soup=OpenSoup(directoryUrl)
    if soup is None:
        return []

    # We need to handle singletons specially
    if directoryUrl.endswith(".html") or directoryUrl.endswith(".htm") or directoryUrl.split("/")[-1:][0] in singletons:
        return ReadSingleton(directoryUrl, fanzineName, soup)

    # By elimination, this must be an ordinary page, so read it.
    # Locate the Index Table on this page.
    table=LocateIndexTable(directoryUrl, soup)
    if table is None:
        return []

    # Check to see if this is marked as a Newszine
    temp=soup.h2
    isnewszines=False
    if temp.text.find("Newszine") > -1:
        Log(f">>>>>> Newszine added: '{fanzineName}'")
        isnewszines=True

    # Try to pull the editor information out of the page
    # The most common format (ignoring a scattering of <br>s) is
    #   H1
    #       series name
    #   /H1
    #   H2
    #       Editor
    #   H2
    #       dates
    #       [Newszine]
    #   /H2
    #   /H2
    #...or something else...

    h2s=str(soup.h2)
    # Split on various flavors of <br> and <h2>
    #pattern="<br>|</br>|<br/>|<BR>|</BR>|<BR/>|<h2>|</h2>|<h2/>|<H2>|</H2>|<H2/>"
    pattern="<.+?>"
    h2s=re.sub(pattern, "|", h2s)
    h2s=h2s.split("|")
    h2s=[h.strip() for h in h2s if len(h.strip()) > 0]

    # Because of the sloppiness of fanac.org, sometime the fanzine name is picked up again here.
    # We ignore the first token if it is too similar to the fanzine name
    if SequenceMatcher(None, h2s[0], fanzineName).ratio() > 0.7:
        h2s=h2s[1:]

    # The editor(s) names are usually the line or lines before the date range.
    # The date range is something like '1964' or '1964-1999' or '1964-1999?'
    pattern="[0-9-\?]"
    editor=""
    for h in h2s:
        if re.match(pattern, h):
            break
        if editor:
            editor+=", "
        editor+=h

    html=str(soup.body)
    country=ExtractCountry(html)
    if country == "":
        Log(f"No country found for {fanzineName}")

    # Walk the table and extract the fanzines in it
    fiiList=ExtractFanzineIndexTableInfo(directoryUrl, fanzineName, table, country)

    if fiiList:
        fsi=FanzineSeriesInfo(SeriesName=fiiList[0].SeriesName, DirURL=directoryUrl, Issuecount=0, Pagecount=0, Editor=editor, Country=country)

        # Add the tags and the series info pointer
        for fii in fiiList:
            fii.Series=fsi
            if isnewszines:
                fii.Taglist.append("newszine")

    return fiiList


#===================================================================================
# The "special biggie" pages are few (only two at the time this ie being written) and need to be handled specially
# The characteristic is that they are a tree of pages which may contain one or more *tagged* fanzine index tables on any level.
# The strategy is to first look for pages at this level, then recursively do the same for any links to a lower level page (same directory)
def ReadSpecialBiggie(directoryUrl: str, fanzineName: str) -> list[FanzineIssueInfo]:

    fiiList: list[FanzineIssueInfo]=[]

    soup=OpenSoup(directoryUrl)
    if soup is None:
        return fiiList

    # Look for and interpret all flagged tables on this page, and look for links to subdirectories.

    # Scan for flagged tables on this page
    table=LocateIndexTable(directoryUrl, soup, silence=True)
    html=str(soup.body)
    country=ExtractCountry(html)
    if country == "":
        Log(f"No country found for {fanzineName}")
    if table is not None:
        fiiList.extend(ExtractFanzineIndexTableInfo(directoryUrl, fanzineName, table, country))

    # Now look for hyperlinks deeper into the directory. (Hyperlinks going outside the directory are not interesting.)
    links=soup.find_all("a")
    for link in links:
        # If it's an html file it's probably worth investigating
        if "href" in link.attrs.keys():     # Some pages have <A NAME="1"> tags which we need to ignore
            url=link.attrs["href"]
            m=re.match("^[a-zA-Z0-9\-_]*.html$", url)
            if m is not None:
                if url.startswith("index") or url.startswith("archive") or url.startswith("Bullsheet1-00") or url.startswith("Bullsheet2-00"):
                    u=ChangeFileInURL(directoryUrl, url)
                    fiiList.extend(ReadSpecialBiggie(u, fanzineName))
    return fiiList


#======================================================================================
# Open a directory's index webpage using BeautifulSoup
def OpenSoup(directoryUrl: str) -> Optional[BeautifulSoup]:
    # Download the index.html, which is
    # * The fanzine's Issue Index Table page
    # * A singleton page
    # * The root of a tree with multiple Issue Index Pages
    Log(f"    opening {directoryUrl}", noNewLine=True)
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
    # soup=BeautifulSoup(h.content, "lxml")   # "html.parser"
    soup=BeautifulSoup(h.content, "html.parser")
    Log("...BeautifulSoup opened")
    return soup


#=====================================================================================
# Function to pull an href and the accompanying text from a Tag
# The structure is "<a href='URL'>LINKTEXT</a>
# We want to extract the URL and LINKTEXT
def GetHrefAndTextFromTag(tag: Tag) -> tuple[str, str]:
    try:
        href=tag.contents[0].attrs.get("href", "")
    except:
        try:
            href=tag.attrs.get("href")
            if href is None:
                href=""
        except:
            return "Failed href in GetHrefAndTextFromTag()", ""

    return tag.contents[0].string, href


#======================================================================================
# Read a singleton-format fanzine page
def ReadSingleton(directoryUrl: str, fanzineName: str, soup) -> list[FanzineIssueInfo]:

    # Usually, a singleton has the information in the first h2 block
    if soup.h2 is None:
        Log("***Failed to find <h2> block in singleton '"+directoryUrl+"'", isError=True)
        return []

    content=[str(e) for e in soup.h2.contents if type(e) is NavigableString]

    # The date is the first line that looks like a date
    date=None
    for c in content:
        date=FanzineDate().Match(c)
        if not date.IsEmpty():
            break
    if date.IsEmpty():
        Log(f"***Failed to find date in <h2> block in singleton '{directoryUrl}'", isError=True)
        return []
    fis=FanzineIssueSpec(FD=date)
    fii=FanzineIssueInfo(SeriesName=fanzineName, IssueName=content[0], DirURL=directoryUrl, PageName="", FIS=fis, Pagecount=0)
    Log(f"   (singleton): {fii}")
    return [fii]


#=====================================================================================
# Function to compress newline elements from a list of Tags.
def RemoveNewlineRows(tags: list[Tag]) -> list[Tag]:
    compressedTags = []
    for row in tags:
        if not isinstance(row, NavigableString):
            compressedTags.append(row)
    return compressedTags


#=========================================================================================
# Read a fanzine's page of any format
def ExtractFanzineIndexTableInfo(directoryUrl: str, fanzineName: str, table: Tag, country: str) -> list[FanzineIssueInfo]:

    # OK, we probably have the issue table.  Now decode it.
    # The first row is the column headers
    # Subsequent rows are fanzine issue rows
    Log(directoryUrl+"\n")

    # Create a composition of all columns. The header column may have newline eleemnts, so compress them out.
    # Then compress out sizes in the actual column header, make them into a list, and then join the list separated by spaces
    table.contents=[t for t in table.contents if not isinstance(t, NavigableString)]
    if len(table.contents[0]) == 0:
        Log("***FanacOrgReaders: No table column headers found. Skipped", isError=True)
    columnHeaders=table.contents[0].text.strip().split("\n")
    columnHeaders: list[str]=[CanonicizeColumnHeaders(c) for c in columnHeaders]

    # We need to pull the fanzine rows in from BeautifulSoup and save them in the same format for later analysis.
    # The format will be a list of rows
    # Each row will be a list of cells
    # Each cell will be either a text string or, if the cell contained a hyperlink, a tuple containing the cell text and the hyperlink
    tableRows: list[list[tuple[str, str]]]=[]
    for i in range(1, len(table)):
        tr: list[Tag]=RemoveNewlineRows(table.contents[i])
        newRow: list[tuple[str, str]]=[]
        for cell in tr:
            newRow.append(GetHrefAndTextFromTag(cell))
        tableRows.append(newRow)

#TODO: We need to skip entries which point to a directory: E.g., Axe in Irish_Fandom
    # Now we process the table rows, extracting the information for each fanzine issue.
    fiiList: list[FanzineIssueInfo]=[]
    for iRow, tableRow in enumerate(tableRows):
        # Skip the column headers row
        if len(tableRow)==1 and tableRow[0]=="\n":  # Skip empty rows
            continue
        Log(f"   row={tableRow}")

        # We need to extract the name, url, year, and vol/issue info for each fanzine
        # We have to treat the Title column specially, since it contains the critical href we need.
        date=ExtractDate(columnHeaders, tableRow)
        ser=ExtractSerial(columnHeaders, tableRow)
        fis=FanzineIssueSpec(FD=date, FS=ser)
        name, href=ExtractHrefAndTitle(columnHeaders, tableRow)
        pages=ExtractPageCount(columnHeaders, tableRow)
        mailings=ExtractMailings(columnHeaders, tableRow)

        # Sometimes we have a reference in one directory be to a fanzine in another. (Sometimes these are duplicate, but this will be taken care of elsewhere.)
        # If the href is a complete fanac.org URL and not relative (i.e, 'http://www.fanac.org/fanzines/FAPA-Misc/FAPA-Misc24-01.html' and not 'FAPA-Misc24-01.html'),
        # we need to check to see if it has directoryURL as a prefix (in which case we delete the prefix) or it has a *different* fanac.org URL, in which case we
        # change the value of directoryURL for this fanzine.
        dirUrl=directoryUrl
        if href is not None:
            if href.startswith(directoryUrl):
                href=href.replace(directoryUrl, "")
                href=href.removeprefix("/")   # Delete any remnant leading "/"
            elif href.startswith("http://www.fanac.org/") or href.startswith("http://fanac.org/") or href.startswith("https://www.fanac.org/") or href.startswith("https://fanac.org/"):
                # OK, this is a fanac URL.  Divide it into a file and a path
                fname=urllib.parse.urlparse(href).path.split("/")[-1:][0]
                if fname:
                    Log(f"   FanacOrgReaders: href='{href}' seems to be pointing to a directory, not a file. Skipped", isError=True)
                    continue
                path=href.replace("/"+fname, "")
                href=fname
                dirUrl=path

        # In cases where there's a two-level index, the dirurl is actually the URL of an html file.
        # We need to remove that filename before using it to form other URLs
        u=urllib.parse.urlparse(dirUrl)     # u is an annoying 6-tuple which needs to be modified and then reassembled
        h, t=os.path.split(u[2])
        if t.lower().endswith(".htm") or t.lower().endswith(".html"):    # If the last part of the URL is a filename (ending in html) then we remove it since we only want the dirname
            t=""
        dirUrl=urllib.parse.urlunparse((u[0], u[1], os.path.join(h, t), u[3], u[4], u[5]))

        # And save the results
        fi=FanzineIssueInfo(SeriesName=fanzineName, IssueName=name, DirURL=dirUrl, PageName=href, FIS=fis, Pagecount=pages, Country=country, Mailing=mailings)
        if fi.IssueName == "<not found>" and fi.FIS.Vol is None and fi.FIS.Year is None and fi.FIS.Month is None:
            Log(f"   ****Skipping null table row: {fi}")
            continue

        Log(f"   {fi}")

        # Append it and log it.
        if fi is not None:
            urlT=""
            if fi.PageName is None:
                urlT="*No PageName*"
            Log(f"Row {iRow}  '{fi.IssueName}'  [{fi.FIS}]  {urlT}")
            fiiList.append(fi)
        else:
            Log(f"{fanzineName}      ***Can't handle {dirUrl}", isError=True)

    return fiiList


#=====================================================================================
# Function to search recursively for the table containing the fanzines listing
# flags is a dictionary of attributes and values to be matched, e.g., {"class" : "indextable", ...}
# We must match all of them
def LookForTable(soup: BeautifulSoup, flags: dict[str, str]) -> Optional[Tag]:

    tables=soup.find_all("table")
    # Look through all tables on the page
    for table in tables:
        # If a table matches *all* of the flags, return the table
        ok=True
        for key in flags.keys():
            if key not in table.attrs or table.attrs[key] is None or table.attrs[key] != flags[key]:
                ok=False
        if ok:
            return table
    return None


#===============================================================================
# Locate a fanzine index table.
def LocateIndexTable(directoryUrl: str, soup: BeautifulSoup, silence: bool=False) -> Optional[Tag]:

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

    # And Toto...
    table=LookForTable(soup, {"border" : "1", "cellpadding" : "2"})
    if table is not None:
        return table

    # Then there's Bable-On...
    table=LookForTable(soup, {"cellpadding" : "10"})
    if table is not None:
        return table

    if not silence:
        Log("***failed because BeautifulSoup found no index table in index.html: "+directoryUrl, isError=True)
    return None
