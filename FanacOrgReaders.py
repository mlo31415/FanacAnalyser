import os
import re
from difflib import SequenceMatcher

from MTVOIDReader import ReadMTVoid
from SharedReaders import TextAndHref, FetchFileFromServer, DecodeTableRow

from FanzineIssueSpecPackage import FanzineIssueInfo, FanzineSeriesInfo
from FanzineIssueSpecPackage import FanzineCounts
from Locale import Locale
from Settings import Settings

from Log import Log, LogSetHeader, LogError
from HelpersPackage import ReadList, FindBracketedText, ParseFirstStringBracketedText, ExtractHTMLUsingFanacStartEndCommentPair
from HelpersPackage import ExtractBetweenHTMLComments, RemoveHyperlink
from HelpersPackage import CanonicizeColumnHeaders, DropTrailingSequenceNumber
from HelpersPackage import ExtractInvisibleTextInsideFanacComment
from HelpersPackage import ParmDict


# ============================================================================================
def ReadFanacFanzineIssues(rootDir: str, fanacDirectories: list[tuple[str, str]]) -> list[FanzineIssueInfo]:
    # Read index.html files on fanac.org
    # We do this by reading the fanzines/<name>/index.html file and then decoding the table in it.
    # What we get out of this is a list of fanzines with name, URL, and issue info.
    # Loop over the list of all fanzines, building up a list of those on fanac.org
    Log("----Begin reading index.html files on fanac.org")

    fanacIssueInfo: list[FanzineIssueInfo]=[]

    # We read in a list of directories to be skipped.
    skippers=ReadList(os.path.join(rootDir, "control-skippers.txt"))

    # Read in a list to be not skipped (implies all other directors are to be skipped.)
    unskippers=ReadList(os.path.join(rootDir, "control-unskippers.txt"))

    # Read the starter -- if present, we scan through classic fanzines until we find this one.
    starter=ReadList(os.path.join(rootDir, "control-startat.txt"))
    # Remove any trailing slash
    starter=[x.removesuffix("/") for x in starter]

    # Some fanzines are listed in our tables, but are offsite and do not even have an index table on fanac.org
    # We also skip these

    offsite=ReadList(os.path.join(rootDir, "control-offsite.txt"))

    fanacDirectories.sort(key=lambda tup: tup[1])
    starterFound=False
    for title, dirname in fanacDirectories:

        pass
        if len(starter) > 0:    # If a starting directory has been specified
            dirname=dirname.removesuffix("/")
            if dirname == starter[0]:
                starterFound=True
            if not starterFound:    # Skip until we find it
                continue

        if len(unskippers) > 0:
            if dirname not in unskippers and (dirname[-1] == "/" and dirname[:-1] not in unskippers):   # Handle dirnames ending in "/"
                continue     # If and only if there are unskippers present, skip directories not in unskippers

        LogSetHeader("'"+dirname+"'      '"+title+"'")

        if dirname in skippers or (dirname[-1] == "/" and dirname[:-1] in skippers):     # Deal with terminal "/"
            LogError(f"...Skipping because it is in skippers: {dirname}")
            continue
        if dirname in offsite:
            Log(f"...Skipping because it is in offsite: {dirname}")
            continue
        # Besides the offsite table, we try to detect references which are offsite from their URLs
        if dirname.startswith("http://"):
            LogError(f"...Skipped because the index page pointed to is not on fanac.org: {dirname}")
            continue

        # The URL we get is relative to the fanzines directory which has the URL fanac.org/fanzines
        # We need to turn it into a URL w can feed to BS4
        if dirname is None:
            continue
        if dirname.startswith("http"):  # We don't want to mess with foreign URLs
            continue
        websiteurl=Settings().Get("Website URL", default="")
        url="https://"+os.path.normpath(os.path.join(websiteurl, dirname)).replace("\\", "/")
        Log(f"{url=}")
        if url is None:
            continue
        m=re.match(r"https://(www.)?fanac.org", url)     # The www. is optional
        if m is None:
            LogError(f"...Skipped because not a fanac.org url: {url}")
            continue

        fanacIssueInfo.extend(ReadFanacFanzineIndexPage(rootDir, title, url))

    # TODO Drop external links which duplicate Fanac.org  (What exactly does this mean??)

    # Remove duplicate FIIs
    deDupDict: dict[str, FanzineIssueInfo]={}
    for fz in fanacIssueInfo:
        deDupDict[fz.DirURL+fz.PageFilename]=fz
    fanacIssueInfo=[x for x in deDupDict.values()]

    if len(fanacIssueInfo) == 0:
        LogError("ReadFanacFanzineIssues: No fanzines found")
        return []

    # Now process the list, doing page and issue counts for each series and adding them to the FanzineSeriesInfo object.
    fanacIssueInfo.sort(key=lambda el: el.Series.SeriesName)
    # With the list in series order, run through and sum up each series
    lastSeries=fanacIssueInfo[0].Series
    count=FanzineCounts()+fanacIssueInfo[0].Pagecount
    for fii in fanacIssueInfo[1:]:
        if lastSeries.SeriesName == fii.Series.SeriesName:
            count+=fii.Pagecount
        else:
            lastSeries.Counts=count
            count=FanzineCounts()+fii.Pagecount
            lastSeries=fii.Series
    lastSeries.Counts=count  # Gotta save that last series count

    # Now fanacIssueList is a list of all the issues of fanzines on fanac.org
    Log("----Done reading index.html files on fanac.org")
    return fanacIssueInfo




# ============================================================================================
def ExtractHeaderCountry(h: str) -> str:
    temp=FindBracketedText(h, "fanac-type")
    if temp[0] is None or len(temp[0]) == 0:
        return ""

    loc=Locale(temp[0])
    Log(f'ExtractCountry: "{temp[0]}" --> {loc}')
    return loc.CountryName

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
# Function to extract fanzine information from a fanac.org fanzine index.html page
def ReadFanacFanzineIndexPage(rootDir: str, fanzineName: str, directoryUrl: str) -> list[FanzineIssueInfo]:

    Log(f"ReadFanacFanzineIndexPage: {fanzineName}  from  {directoryUrl}")

    # MT Void has special handling.
    if fanzineName == "MT Void, The":
        return ReadMTVoid("https://fanac.org/fanzines/MT_Void/")

    # Fanzines with only a single page rather than an index.
    # Note that these are directory names
    global singletons   # Not actually used anywhere else, but, for performance sake, should be read once and retained
    try:
        singletons
    except NameError:
        singletons=ReadList(os.path.join(rootDir, "control-singletons.txt"))

    # It looks like this is a single level directory.
    html=FetchFileFromServer(directoryUrl)
    if html is None:
        LogError(f"ReadFanacFanzineIndexPage: Failed to fetch {directoryUrl}. Not processed.")
        return []

    # Get the FIP version
    #html=html.replace(r"ü", "&Uuml;")
    version=ExtractInvisibleTextInsideFanacComment(html, "fanzine index page V")       #<!-- fanac-fanzine index page V2-->

    if version == "":
        return ReadFanacFanzineIndexPageOldNoSoup(fanzineName, directoryUrl, html)
    else:
        return ReadFanacFanzineIndexPageNew(fanzineName, directoryUrl, html)


def ReadFanacFanzineIndexPageNew(fanzineName: str, directoryUrl: str, html: str) -> list[FanzineIssueInfo]:
    if html is None:
        return []

    # Check to see if this is marked as a Newszine
    fztype=ExtractBetweenHTMLComments(html, "type")
    isnewszines="Newszine" == fztype

    # Extract any fanac keywords.  They will be of the form:
    #       <! fanac-keywords: xxxxx -->
    # There may be many of them
    kwds: ParmDict=ParmDict(CaseInsensitiveCompare=True)
    keywords=ExtractInvisibleTextInsideFanacComment(html, "keywords")
    if keywords != "":
        keywords=[x.strip() for x in keywords.split(";")]
        for keyword in keywords:
            kwds[keyword]=""    # We just set a value of the empty string.  Missing keywords will return None

    seriesName=ExtractBetweenHTMLComments(html, "name")
    seriesName=re.sub(r"</?br/?>", "; ", seriesName, flags=re.IGNORECASE)    # Replace internal <br> with semicolons

    editors=ExtractBetweenHTMLComments(html, "eds")
    editors=editors.replace("<br/>", "<br>").replace("\n", "<br>")
    editors=[RemoveHyperlink(x).strip() for x in editors.split("<br>")]
    editors=[x for x in editors if len(x.strip()) > 0]
    editors=", ".join(editors)
    country=ExtractBetweenHTMLComments(html, "loc")
    if country == "":
        Log(f"No location found for {fanzineName}")

    # Walk the table and extract the fanzines in it
    # # The table is bounded by <!-- fanac-table-headers start--> and <!-- fanac-table-rows end-->
    # m=re.match(r".*<!-- fanac-table-headers start-->(.*)<!-- fanac-table-rows end-->", html, flags=re.IGNORECASE|re.DOTALL)
    # if m is None:
    #     assert False
    fiiList=ExtractFanzineIndexTableInfoOldNoSoup(directoryUrl, fanzineName, html, editors, country, fztype, alphabetizeIndividually=True, useNewTableStructure=True)

    # Some series pages have the fanzine type "Collection".  If present, we create a series entry for *each* individual issue on the page.
    # Some early series pages have the keyword "Alphabetize individually".  This is the same as being a Collection, but is otherwise ignored.
    if kwds["Alphabetize individually"] is not None or fztype.lower() == "collection":

        # Add the tags and the series info pointer
        for fii in fiiList:
            # Create a special series just for this issue.
            fii.Series=FanzineSeriesInfo(SeriesName=DropTrailingSequenceNumber(fii.IssueName), DirURL=directoryUrl, Issuecount=1, Pagecount=0, Editor=fii.Editor, Country=country, AlphabetizeIndividually=True, Keywords=kwds)
            if isnewszines:
                fii.Taglist.append("newszine")
    else:
        # This is the normal case with a fanzines series containing multiple issues. Add the tags and the series info pointer
        fsi=FanzineSeriesInfo(SeriesName=seriesName, DirURL=directoryUrl, Issuecount=0, Pagecount=0, Editor=editors, Country=country, Keywords=kwds)
        for fii in fiiList:
            fii.Series=fsi
            if isnewszines:
                fii.Taglist.append("newszine")

    return fiiList


def ReadFanacFanzineIndexPageOldNoSoup(fanzineName: str, directoryUrl: str, html: str) -> list[FanzineIssueInfo]:
    # By elimination, this must be an ordinary page, so read it.
    # Locate the Index Table on this page.

    # Check to see if this is marked as a Newszine
    isnewszines=False
    if html.find("Newszine") > -1:
        Log(f">>>>>> Newszine added: '{fanzineName}'")
        isnewszines=True

    # Extract any fanac keywords.  They will be of the form:
    #       <! fanac-keywords: xxxxx -->
    # There may be many of them
    contents=html
    contents=contents.replace("\n", " ")
    kwds: ParmDict=ParmDict(CaseInsensitiveCompare=True)
    pat=r"<!--\s?[Ff]anac-keywords:(.*?)-{1,4}>"
    while True:
        m=re.search(pat, contents)#, re.IGNORECASE)
        if not m:
            break
        kwds[m.groups()[0].strip()]=""
        contents=re.sub(pat, "", contents)#, re.IGNORECASE)

    # While we expect the H1 title material to be delimited by <h2> and <br>, but we can't count on that, so we look for a terminal </h1>
    leading, h1s, trailing=ParseFirstStringBracketedText(html, "h1", IgnoreCase=True)
    topblock=None
    if h1s != "" :
        html=leading+" "+trailing
        topblock=h1s

    if topblock is None:
        m=re.search(rf'<!--\s*h1\s*(class="sansserif")?>(.*?)<!--\s*/h1\s*-->', h1s, flags=re.IGNORECASE|re.DOTALL)
        if m is not None:
            ret=m.groups()[1].strip()
            if ret != "":
                topblock=ret

    if topblock is None:
        Log(f"***********************************\n*** No top block found in {directoryUrl}\n***********************************")
        return []

    items=re.split(r"(</?h1>|</?h2>|<br>)+", topblock, flags=re.IGNORECASE | re.DOTALL)
    items=[x.strip() for x in items]    # Strip all items
    items=[x for x in items if len(x) > 0]  # Remove empty entries
    items=[x for x in items if len(x) == 1 or (len(x) > 1 and not (x[0] == "<" and x[-1] == ">"))]     # Remove entries entirely contained in <>
    items=[x for x in items if x.lower() != "<br>"]
    if len(items) == 4:
        t1=items[0]
        # Because of the sloppiness of fanac.org, sometimes the fanzine name is picked up again here.
        # We ignore the first token if it is too similar to the fanzine name
        if SequenceMatcher(None, t1, fanzineName).ratio() > 0.7:
            t1=t1[1:]

    # The usual order of the top stuff is
        # Series name
        # editors (sometimes in two or more items)
        # dates (1990? or 1956-57 or 1956??-1999??) maybe spaces around "-"
        # Fanzine Type

    listOfFanzineTypes=["fanzine", "genzine", "newszine", "collection", "apazine"]

    # First, look for a date range.  This will pin down the number of editors.
    dateindex=None
    for i, item in enumerate(items):
        m=re.match(r"^[0-9]*\?* *- *[0-9]*\?*$", item)
        if m is not None:
            dateindex=i
            break

    # If a date is found, then there should be either 0 or one items after it.  If there is 1, then it's the fanzine type
    fanzineType=""
    if dateindex is not None:
        if dateindex < len(items)-1:
            fanzineType=items[-1]

        # And all the items before the date are series and editors
        items=items[:dateindex]

    else:
        # If no date is found, check the last item to see if it's a fanzine type.
        if items[-1].lower in listOfFanzineTypes:
            fanzineType=items[-1]
            fanzineType[0]=fanzineType[0].Upper()
        items=items[:-1]

    # Now we want to find the series name and editors
    # This will normally be
    #   series name
    #   editor, [editor, ...]
    #   But sometimes a "/" will be used and sometimes the editors will appear on separate lines

    # The easy case: There are two items
    editors: str=""
    seriesName: str=""
    if len(items) == 2:
        seriesName=items[0]
        editors=items[1]

    elif len(items) < 2:
        # When there is only one item for editor and title, it's almost always the editor which has been left out.
        # This is usually because there were many, so we set the editor "various"
        editors="various"
        seriesName=items[0]

    elif len(items) > 2:
        seriesName=items[0]
        editors=", ".join(items[1:])

    # Make sure the editors and "," separated and not "/" or "//" separated
    editors=editors.replace("//", ",").replace("/", ",")

    country=ExtractHeaderCountry(html)
    if country == "":
        Log(f"No country found for {fanzineName}")

    # Walk the table and extract the fanzines in it
    fiiList=ExtractFanzineIndexTableInfoOldNoSoup(directoryUrl, fanzineName, html, editors, country, fanzineType, alphabetizeIndividually=True)

    # Some old-style pages may have a hand-edited "alphabetize individually" keywork.  Test for that as well as for type=Collection.
    if kwds["Alphabetize individually"] is not None or fanzineType == "Collection":
        # Add the tags and the series info pointer
        for fii in fiiList:
            # Create a special series just for this issue.
            fii.Series=FanzineSeriesInfo(SeriesName=fii.IssueName, DirURL=directoryUrl, Issuecount=1, Pagecount=0, Editor=fii.Editor, Country=country, AlphabetizeIndividually=True, Keywords=kwds)
            if isnewszines:
                fii.Taglist.append("newszine")
    else:
        # This is the normal case with a fanzines series containing multiple issues. Add the tags and the series info pointer
        fsi=FanzineSeriesInfo(SeriesName=seriesName, DirURL=directoryUrl, Issuecount=0, Pagecount=0, Editor=editors, Country=country, Keywords=kwds)
        for fii in fiiList:
            fii.Series=fsi
            if isnewszines:
                fii.Taglist.append("newszine")

    return fiiList


#=========================================================================================
# Read a fanzine's page of any format
def ExtractFanzineIndexTableInfoOldNoSoup(directoryUrl: str, fanzineName: str, html: str, editor: str, defaultcountry: str, fanzineType: str="",
    alphabetizeIndividually: bool=False, useNewTableStructure: bool=False) -> list[FanzineIssueInfo]:

    Log(directoryUrl+"\n")

    # OK, we probably have the issue table.  Now decode it.
    # The first row is the column headers
    # Subsequent rows are fanzine issue rows
    if useNewTableStructure:
        headerTable=ExtractHTMLUsingFanacStartEndCommentPair(html, "table-headers")
        # At this point, we should just have <TH>xxxxx</TH> column headers
        _, row=ReadTableRow(headerTable, "TR", "TH")
        bodyTable=ExtractHTMLUsingFanacStartEndCommentPair(html, "table-rows")
    else:
        # First, locate the FIP main table.
        m=re.search(r'<TABLE BORDER="1" STYLE="border-collapse:collapse" CELLPADDING="[0-9]+">', html, flags=re.IGNORECASE|re.DOTALL)  #This seems to be used in all old pages
        if m is None:
            assert False
        m.end()
        loc=m.end()

        locend=html[loc:].find('</TABLE>')
        if locend == -1:
            assert False

        headerTable=html[loc:loc+locend]
        bodyTable, row=ReadTableRow(headerTable, "TR", "TH")

    columnHeaders: list[str]=[CanonicizeColumnHeaders(c.Text) for c in row] # Canonicize and return to being just a str list

    # The mailing column may contain hyperlinks.  Suppress them, leaving only the link text.
    mailingCol=None
    if "Mailing" in columnHeaders:
        mailingCol=columnHeaders.index("Mailing")

    # Now loop through the body getting the rows
    rows: list[list[TextAndHref]]=[]
    while len(bodyTable) > 0:
        bodyTable, row=ReadTableRow(bodyTable, "TR", "TD")
        if len(row) == 0:
            break
        for i, cell in enumerate(row):    # Turn '<BR>' into empty string
            if cell.Text.lower() == "<br>":
                row[i].Text=""
        if mailingCol is not None and mailingCol <len(row):
            if row[mailingCol].Text != "":
                row[mailingCol].Url=""    # Get rid of any hyperlinks

        rows.append(row)

#TODO: We need to skip entries which point to a directory: E.g., Axe in Irish_Fandom
    # Now we process the table rows, extracting the information for each fanzine issue.
    fiiList: list[FanzineIssueInfo]=[]
    for iRow, tableRow in enumerate(rows):
        # Skip null rows
        if len(tableRow) == 0 or (len(tableRow) == 1 and len(tableRow[0].Text.strip()) == 0):
            continue
        Log(f"   {tableRow=}")

        # The first element of the table sometimes comes in with embedded non-breaking spaces which must be turned to real spaces.
        # (They were apparently put there deliberately some time in the past.)
        # if len(tableRow[0].Text) > 0 and tableRow[0].Text != "":  # Some empty rows have no entry in col 1, not even an empty string
        #     tableRow[0]=TextAndHref(RemoveFunnyWhitespace(tableRow[0].Text), tableRow[0].Url)

        # We need to extract the name, url, year, and vol/issue info for each fanzine
        # We have to treat the Text column specially, since it contains the critical href we need.
        fi=DecodeTableRow(columnHeaders, tableRow, iRow, defaultcountry, editor, fanzineType, alphabetizeIndividually, directoryUrl)
        if fi is None:
            continue

        Log(f"   {fi=}")

        # Append it and log it.
        if fi is not None:
            urlT=""
            if fi.PageFilename == "":
                urlT="*No PageName*"
            Log(f"Row {iRow}  '{fi.IssueName}'  [{fi.FIS}]  {urlT}")
            fiiList.append(fi)
        else:
            assert False #LogError(f"{fanzineName}      ***Can't handle {dirUrl}")

    return fiiList


def ReadTableRow(tablein: str, rowdelim, coldelim: str) -> tuple[str, list[TextAndHref]]:

    tabletext=tablein.strip()
    rowstext=""
    if len(tabletext) > 0:
        # Look for the stuff bounded by <TR>...</TR> which will be the rows html. (By this point we have already dealt with the column header html.)
        tabletext=tabletext.replace(r"\n", " ").strip()
        m=re.match(rf"<{rowdelim}>(.*?)</{rowdelim}>", tabletext, re.IGNORECASE | re.DOTALL)
        if m is None:
            assert False
            #return tabletext, row
        rowstext=m.group(1).strip()
        tabletext=tabletext[m.end():].strip()

    # Extract the rows from the rows html
    row: list[TextAndHref] = []
    while len(rowstext) > 0:
        m=re.match(rf"<{coldelim} *([^>]*?)>(.*?)</{coldelim}>", rowstext, re.IGNORECASE)
        if m is None:
            break
        row.append(TextAndHref(m.group(2).strip()))
        end=m.end()

        # Look for a colspan= in the 1st column
        m=re.match(r".*?colspan=['\"]([0-9]+)['\"]", m.group(1), re.IGNORECASE)
        if m is not None:   # We have a colspan.  Add empty columns following.
            csVal=int(m.group(1).strip())
            ncols=int(csVal)-1
            for i in range(ncols):
                row.append(TextAndHref())
            # Insert the colspn information in the 2nd column
            row[1]=TextAndHref(f'colspan="{csVal}"', "")
        rowstext=rowstext[end:].strip()

    return tabletext, row

