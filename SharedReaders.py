from typing import Self, Union

import re
import os
from contextlib import suppress
import requests
import time

#from bs4 import NavigableString, Tag
import urllib.parse

from Log import Log, LogError
from FanzineIssueSpecPackage import FanzineIssueInfo, FanzineIssueSpec, FanzineDate, FanzineSerial

from HelpersPackage import CanonicizeColumnHeaders, FindHrefInString #, RemoveFunnyWhitespace
from HelpersPackage import Int0, InterpretNumber, InterpretInteger


class TextAndHref:
    # It accepts three initialization calls:
    #   TextAnHref(str)  -->   Attempt to turn it into text+href; if this fails it's just text
    #   TextAndHref(TextAndHref)  -- >  just make a copy
    #   TextAndHref(text, href)  -->  just assemble the arguments into a TextAndHref(
    def __init__(self, text: str|Self="", href: str|None=None):
        self.Url: str=""
        self.Text: str=""

        if href is None:
            if isinstance(text, TextAndHref):
                self.Url=text.Url
                self.Text=text.Text.strip()
                return

            _, self.Url, self.Text, _=FindHrefInString(text)
            if self.Url == "" and self.Text == "":  # Did FindHrefInString() failed to make sense of the input?
                self.Text=text.strip()
            return

        # Both arguments were supplied
        self.Text=text.strip()
        self.Url=href

    def IsEmpty(self) -> bool:
        return self.Text == "" and self.Url == ""

    def __str__(self) -> str:
        if self.Url == "":
            return f"{self.Text})"
        return f"<a href={self.Url}>{self.Text}</a>>"

    def __repr__(self) -> str:
        if self.Url == "":
            return f"TextAndHref('{self.Text}')"
        return f"TextAndHref(Text='{self.Text}', Url='{self.Url}')"

# #=========================================================================================
# # Read a fanzine's page of any format
# def ExtractFanzineIndexTableInfoOld(directoryUrl: str, fanzineName: str, table: Tag, editor: str, defaultcountry: str, fanzineType: str="", alphabetizeIndividually: bool=False) -> list[FanzineIssueInfo]:
#
#     # OK, we probably have the issue table.  Now decode it.
#     # The first row is the column headers
#     # Subsequent rows are fanzine issue rows
#     Log(directoryUrl+"\n")
#
#     # Create a composition of all columns. The header column may have newline elements, so compress them out.
#     # Then compress out sizes in the actual column header, make them into a list, and then join the list separated by spaces
#     table.contents=[t for t in table.contents if not isinstance(t, NavigableString)]
#     if len(table.contents[0].text) == 0:
#         LogError("***FanacOrgReaders: No table column headers found. Skipped")
#     columnHeaders=re.split(r"\\n|\n", table.contents[0].text.strip())
#     columnHeaders=[x for x in columnHeaders if x != ""]
#     columnHeaders: list[str]=[CanonicizeColumnHeaders(c) for c in columnHeaders]
#
#     # The format will be a list of rows
#     # Each row will be a list of cells
#     # Each cell will be either a text string (usually a "/n") or a cell containing the table contents.
#     # If a content cell contains a hyperlink, a TextAndHref containing the cell text and the hyperlink
#     # If it's plain text, a TextAndHref with an empty href
#     tableRows: list[list[list[TextAndHref]]]=[[]]
#     for row in table.contents[1:]:  # Skip the first row
#         if type(row) is not Tag:
#             Log(f"This should be a tag, but isn't. Skipped: {row}")
#             continue
#         tr=row.contents
#
#         newRow: list[list[TextAndHref]]=[]
#         for cell in tr:
#             if not isinstance(cell, NavigableString):    # Half the rows are newlines which we might as well ignore now
#                 newRow.append(GetTextAndHrefFromTag(cell))
#         tableRows.append(newRow)
#
# #TODO: Do we need to skip entries which point to a directory: E.g., Axe in Irish_Fandom?
#     # Now we process the table rows, extracting the information for each fanzine issue.
#     fiiList: list[FanzineIssueInfo]=[]
#     for iRow, tableRow in enumerate(tableRows):
#         # Skip the column headers row and null rows
#         if len(tableRow) == 0 or (len(tableRow) == 1 and tableRow[0]=="\n"):
#             continue
#         Log(f"   {tableRow=}")
#
#         # The first element of the table sometimes comes in with embedded non-breaking spaces which must be turned to real spaces.
#         # (They were apparently put there deliberately some time in the past.)
#         if len(tableRow[0]) > 0 and tableRow[0].Text != "":  # Some empty rows have no entry in col 1, not even an empty string
#             tableRow[0][0]=TextAndHref(RemoveFunnyWhitespace(tableRow[0][0].Text), tableRow[0][0].Url)
#
#         fi=DecodeTableRow(columnHeaders, tableRow, iRow, defaultcountry, editor, fanzineType, alphabetizeIndividually, directoryUrl)
#         if fi is None:
#             continue
#
#         Log(f"   {fi=}")
#
#         # Append it and log it.
#         if fi is not None:
#             urlT=""
#             if fi.PageFilename == "":
#                 urlT="*No PageName*"
#             Log(f"Row {iRow}  '{fi.IssueName}'  [{fi.FIS}]  {urlT}")
#             fiiList.append(fi)
#         else:
#             assert False  #LogError(f"{fanzineName}      ***Can't handle {dirUrl}")
#
#     return fiiList


def DecodeTableRow(columnHeaders: list[str], tableRow: list[TextAndHref], iRow: int, defaultcountry: str, defaultEditor: str, fanzineType: str, alphabetizeIndividually: bool, directoryUrl: str) -> FanzineIssueInfo|None:
    # We need to extract the name, url, year, and vol/issue info for each fanzine
    # We have to treat the Text column specially, since it contains the critical href we need.
    date=ExtractDate(columnHeaders, tableRow)
    ser=ExtractSerial(columnHeaders, tableRow)
    fis=FanzineIssueSpec(FD=date, FS=ser)
    title=ExtractIssueNameAndHref(columnHeaders, tableRow)
    if "fanac.org/fanzines/" in title.Url.lower() and title.Url[-1] == "/":
        return  # This is an independent fanzine index page referred to in this FIP. It will be dealt with on its own and can be skipped for now.
    pages=ExtractPageCount(columnHeaders, tableRow)
    mailings=ExtractMailings(columnHeaders, tableRow)
    country=ExtractRowCountry(columnHeaders, tableRow, defaultcountry)
    ed=defaultEditor
    if alphabetizeIndividually:
        lineEditor=ExtractEditor(columnHeaders, tableRow)
        if lineEditor != "":
            ed=lineEditor

    # Sometimes we have a reference in one directory be to a fanzine in another. (Sometimes these are duplicate, but this will be taken care of elsewhere.)
    # If the href is a complete fanac.org URL and not relative (i.e, 'http://www.fanac.org/fanzines/FAPA-Misc/FAPA-Misc24-01.html' and not 'FAPA-Misc24-01.html'),
    # we need to check to see if it has directoryURL as a prefix (in which case we delete the prefix) or it has a *different* fanac.org URL, in which case we
    # change the value of directoryURL for this fanzine.
    dirUrl=directoryUrl
    dir=urllib.parse.urlparse(dirUrl).path.split("/")[2]
    if title.Url != "":
        if title.Url.startswith(directoryUrl):
            title.Url=title.Url.replace(directoryUrl, "")
            title.Url=title.Url.removeprefix("/")  # Delete any remnant leading "/"

        elif title.Url.startswith("http://www.fanac.org/") or title.Url.startswith("http://fanac.org/") or title.Url.startswith("https://www.fanac.org/") or title.Url.startswith("https://fanac.org/"):
            # OK, this is a fanac URL.  Divide it into a file and a path
            parts=urllib.parse.urlparse(title.Url).path.split("/")
            fname=parts[-1:][0]
            if not fname.lower().endswith((".html", ".htm", ".pdf")):
                LogError(f"   FanacOrgReaders: href='{title.Url}' seems to be pointing to something not ending in an allowed extension. Skipped")
                return None
            path=title.Url.replace("/"+fname, "")
            title.Url=fname
            dirUrl=path

    # In cases where there's a two-level index, the dirurl is actually the URL of an html file.
    # We need to remove that filename before using it to form other URLs
    u=urllib.parse.urlparse(dirUrl)  # u is an annoying 6-tuple which needs to be modified and then reassembled
    h, t=os.path.split(u[2])
    if t.lower().endswith(".htm") or t.lower().endswith(".html"):  # If the last part of the URL is a filename (ending in html) then we remove it since we only want the dirname
        t=""
    dirUrl=str(urllib.parse.urlunparse((u[0], u[1], os.path.join(h, t), u[3], u[4], u[5])))

    # And save the results
    fi=FanzineIssueInfo(IssueName=title.Text, DirURL=dirUrl, PageFilename=title.Url, FIS=fis, Position=iRow, Pagecount=pages, Editor=ed, Country=country, Mailings=mailings,
                        FanzineType=fanzineType, AlphabetizeIndividually=alphabetizeIndividually)
    if fi.IssueName == "<not found>" and fi.FIS.Vol is None and fi.FIS.Year is None and fi.FIS.MonthNum is None:
        Log(f"   ****Skipping null table row (#1): {fi}")
        return None

    return fi


# #=====================================================================================
# # Function to pull an href and the accompanying text from a Tag
# # The structure is "<a href='URL'>LINKTEXT</a>
# # We want to extract the URL and LINKTEXT
# def GetTextAndHrefFromTag(cell: Tag) -> list[TextAndHref]:
#     out=[]
#     for thing in cell:
#         if isinstance(thing, Tag):
#             try:
#                 href=thing.attrs.get("href", "")
#             except:
#                 try:
#                     href=cell.attrs.get("href")
#                     if href is None:
#                         href=""
#                 except:
#                     return [TextAndHref("Failed href in GetHrefAndTextFromTag()", "")]
#
#             tag=thing.string
#             if tag is None:
#                 tag=""
#             out.append(TextAndHref(tag, href))
#         else:
#             out.append(TextAndHref(str(thing), ""))
#
#     return out



#=============================================================================================
# Extract a date from a table row.  Note that this will usually involved merging data from multiple columns.
# We return a FanzineDate
def ExtractDate(columnHeaders: list[str], row: list[TextAndHref]) -> FanzineDate:

    # Does this have a Date column?  If so, that's all we need. (I hope...)
    dateText=GetCellValueByColHeader(columnHeaders, row, "Date").Text
    if dateText is not None and len(dateText) > 0:
        # Get the date
        with suppress(Exception):
            return FanzineDate().Match(dateText)

    # Next, take the various parts and assemble them and try to interpret the result using the FanzineDate() parser
    yearText=GetCellValueByColHeader(columnHeaders, row, "Year").Text
    monthText=GetCellValueByColHeader(columnHeaders, row, "Month").Text
    dayText=GetCellValueByColHeader(columnHeaders, row, "Day").Text
    dateText=GetCellValueByColHeader(columnHeaders, row, "Date").Text

    if yearText is not None and yearText != "":
        fd=FanzineDate(YearText=yearText, MonthText=monthText, Day=dayText, DateText=dateText)
        return fd

    Log("   ***Date conversion failed: no usable date columns data found")
    return FanzineDate()

#=============================================================================================
# Extract a serial number (vol, num, whole_num) from a table row
# We return a FanzineSerial object
# This may involve merging data from multiple columns
def ExtractSerial(columnHeaders: list[str], row: list[TextAndHref]) -> FanzineSerial:

    wholeText=GetCellValueByColHeader(columnHeaders, row, "Whole").Text
    volText=GetCellValueByColHeader(columnHeaders, row, "Volume").Text
    numText=GetCellValueByColHeader(columnHeaders, row, "Number").Text
    volNumText=GetCellValueByColHeader(columnHeaders, row, "VolNum").Text
    if type(volNumText) is tuple:
        volNumText=volNumText[0]

    titleText=GetCellValueByColHeader(columnHeaders, row, ["Text", "Issue"]).Text

    return ExtractSerialNumber(volText, numText, wholeText, volNumText, titleText)


#============================================================================================
# Find the cell containing the editor's name and return its value
def ExtractEditor(columnHeaders: list[str], row: list[TextAndHref]) -> str:

    editorText=GetCellValueByColHeader(columnHeaders, row, ["Editor", "Editors", "Author", "Authors", "Editor/Publisher"]).Text
    if editorText is None:
        return ""

    return editorText

#============================================================================================
# Find the cell containing the page count and return its value
def ExtractPageCount(columnHeaders: list[str], row: list[TextAndHref]) -> int:

    pageCountText=GetCellValueByColHeader(columnHeaders, row, ["Pages", "Pp.", "Page"]).Text
    if pageCountText is None:
        # If there's no column labelled for page count, check to see if there's a "Type" column with value "CARD".
        # These are newscards and are by definition a single page.
        typeText=GetCellValueByColHeader(columnHeaders, row, "Type").Text
        if typeText is not None and typeText.lower() == "card":
            return 1    # All cards have a pagecount of 1
        return 0

    return Int0(pageCountText)


#============================================================================================
# Find the cell containing the page count and return its value
def ExtractRowCountry(columnHeaders: list[str], row: list[TextAndHref], defaultcountry: str) -> str:

    country=GetCellValueByColHeader(columnHeaders, row, ["Country"]).Text
    if country is None or country == "":
        return defaultcountry

    return country.strip()



#=============================================================================================
# Given a list of alternative possible column headers and a list of row cell values, return the first cell matching one of the headers
# If cellname is a list of names, try them all and return the first that hits
def GetCellValueByColHeader(columnHeaders: list, row: list[TextAndHref], cellnamealternatives: Union[str, list[str]]) -> TextAndHref | None:

    # Make sure cell names can be a list or a singleton. Make sure it is a list we can iterate over
    cellnamealternativeslist=cellnamealternatives if type(cellnamealternatives) is list else [cellnamealternatives]
    for cn in cellnamealternativeslist:        # Iterate over the list of cell names sought
        cellNameSought=CanonicizeColumnHeaders(cn)
        # Run through the list of column headers looking for a match
        for i, header in enumerate(columnHeaders):
            if CanonicizeColumnHeaders(header) == cellNameSought:
                # Deal with missing cells -- apparently due to an LST read problem with certain mal-formed LST files
                try:
                    if cellNameSought == "Mailings":
                        # If there's an href in the cell, we need to see if there are mulitple.  Likewise if there are none.
                        if row[i].Text.lower().count("href=") > 1:
                            split=re.split(r"> *[,&] *<", row[i].Text, flags=re.IGNORECASE)
                            tahs=[]
                            for sp in split:    # re.split trims away some starting and ending <>. Restore them.
                                sp=sp.strip()
                                if sp[-1] != ">":
                                    sp=sp+">"
                                if sp[0] != "<":
                                    sp="<"+sp
                                tahs.append(TextAndHref(sp))
                            assert False    # Do we need to handle this case?
                            return tahs
                    return TextAndHref(row[i])  # Note that this handles both pure text and TextAndHref cell values returning a TextAndHref value
                except:
                    return TextAndHref()

    return TextAndHref()

# ============================================================================================
# Scan the row and locate the issue cell, title and href and return them as a tuple
def ExtractIssueNameAndHref(columnHeaders: list[str], row: list[TextAndHref]) -> TextAndHref:
    if len(row) < len(columnHeaders):
        Log(f"ExtractIssueNameAndHref: Row has {len(row)} columns while we expected {len(columnHeaders)} columns. Row skipped.")
        return TextAndHref()

    # Find the column containing the issue name.  There are several possibilities.
    issue=GetCellValueByColHeader(columnHeaders, row, "Issue")
    if issue.IsEmpty():
        issue=GetCellValueByColHeader(columnHeaders, row, "Title")
    if issue.IsEmpty():
        issue=GetCellValueByColHeader(columnHeaders, row, "Text")
    if issue.IsEmpty():
       return TextAndHref("<not found>", "")

    # If we already have found a URL, we're done.
    if issue.Url != "":
        return issue

    # We now know the there is no URL.  If there's no text, either, return an empty TextAndHref
    if issue.Text == "":
        return TextAndHref()

    # Sometimes the title of the fanzine is in one column and the hyperlink to the issue in another.
    # If we don't find a hyperlink in the title, scan the other cells of the row for the first col containing a hyperlink
    # We return the name from the issue cell and the hyperlink from the other cell
    for i in range(0, len(columnHeaders)):
        if len(row) > 0 and row[i].Url != "":
            return TextAndHref(issue.Text, row[i].Url)

    return issue     # No hyperlink found

# # ============================================================================================
# # Scan the row and locate the issue cell, title and href and return them as a tuple
# def ExtractIssueNameAndHref(columnHeaders: list[str], row: list[TextAndHref]) -> TextAndHref:
#     if len(row) < len(columnHeaders):
#         Log(f"ExtractIssueNameAndHref: Row has {len(row)} columns while we expected {len(columnHeaders)} columns. Row skipped.")
#         return TextAndHref()
#
#     # Find the column containing the issue name.  There are several possibilities.
#     issue=GetCellValueByColHeader(columnHeaders, row, "Issue")
#     if issue.IsEmpty():
#         issue=GetCellValueByColHeader(columnHeaders, row, "Title")
#     if issue.IsEmpty():
#         issue=GetCellValueByColHeader(columnHeaders, row, "Text")
#     if issue.IsEmpty():
#        return TextAndHref("<not found>", "")
#
#     # If we already have found a URL, we're done.
#     if issue.Url != "":
#         return issue
#
#     # We now know the there is no URL.  If there's no text, either, return an empty TextAndHref
#     if issue.Text == "":
#         return TextAndHref()
#
#     # Sometimes the title of the fanzine is in one column and the hyperlink to the issue in another.
#     # If we don't find a hyperlink in the title, scan the other cells of the row for the first col containing a hyperlink
#     # We return the name from the issue cell and the hyperlink from the other cell
#     for i in range(0, len(columnHeaders)):
#         if len(row) > 0 and row[i].Url != "":
#             return TextAndHref(issue.Text, row[i].Url)
#
#     return issue     # No hyperlink found


#============================================================================================
# Find the cell containing the mailings data
def ExtractMailings(columnHeaders: list[str], row: list[TextAndHref]) -> list[str]:

    mailingVals=GetCellValueByColHeader(columnHeaders, row, "Mailing")
    if len(mailingVals.Text) == 0:
        return []

    # The mailing text is a series of APA names followed by alphanumerics separated by ampersands or commas
    mailingslist=[]

    mailingtext=mailingVals.Text
    while len(mailingtext) > 0:
        # This next little bit calls subber() each time re.sub find a match
        # This results in the matches getting appended to mailingslist
        def subber(m) -> str:
            mailingslist.append(m.groups()[0])
            return ""

        mailingtext=re.sub(r"([a-zA-Z0-9'\-:]+\s+[0-9]+[a-zA-Z]*)[,&]\s*", subber, mailingtext)
        if len(mailingtext) > 0:
            mailingslist.append(mailingtext)
            break

    return mailingslist


#==============================================================================
# Given the contents of various table columns, attempt to extract serial information
# This uses InterpretSerial for detailed decoding
def ExtractSerialNumber(volText: str, numText: str, wholeText: str, volNumText: str, titleText: str) -> FanzineSerial:
    wholeInt=None
    volInt=None
    numInt=None
    numsuffix=None
    maybeWholeInt=None
    wsuffix=None

    if wholeText is not None:
        wholeInt=InterpretNumber(wholeText)

    if volNumText is not None:
        ser=FanzineSerial().Match(volNumText)
        if ser.Vol is not None and ser.Num is not None:  # Otherwise, we don't actually have a volume+number
            volInt=ser.Vol
            numInt=ser.Num
            numsuffix=ser.NumSuffix

    if volText is not None:
        volInt=InterpretInteger(volText)

    # If there's no vol, anything under "Num", etc., must actually be a whole number
    if volText is None:
        with suppress(Exception):
            maybeWholeText=numText
            maybeWholeInt=int(maybeWholeText)
            numText=None

    # But if there *is* a volume specified, than any number not labelled "whole" must be a number within the volume
    if volText is not None and numText is not None:
        numInt=InterpretInteger(numText)

    # OK, now figure out the vol, num and whole.
    # First, if a Vol is present, and an unambigious Num is absent, the an ambigious Num must be the Vol's num
    if volInt is not None and numInt is None and maybeWholeInt is not None:
        numInt=maybeWholeInt
        maybeWholeInt=None

    # If the wholeInt is missing and maybeWholeInt hasn't been used up, make it the wholeInt
    if wholeInt is None and maybeWholeInt is not None:
        wholeInt=maybeWholeInt

    # Next, look at the title -- titles often have a serial designation at their end.

    if titleText is not None:
        # Possible formats:
        #   n   -- a whole number
        #   n.m -- a decimal number
        #   Vn  -- a volume number, but where's the issue?
        #   Vn[,] #m  -- a volume and number-within-volume
        #   Vn.m -- ditto
        ser=FanzineSerial().Match(titleText if not isinstance(titleText, list) else titleText[0])

        # Some indexes have fanzine names ending in <month> <year>.  We'll detect these by looking for a trailing number between 1930 and 2050, and reject
        # getting vol/ser, etc., from the title if we find it.
        if ser.Num is None or ser.Num < 1930 or ser.Num > 2050:

            if ser.Vol is not None and ser.Num is not None:
                if volInt is None:
                    volInt=ser.Vol
                if numInt is None:
                    numInt=ser.Num

                if volInt != ser.Vol:
                    LogError("***Inconsistent serial designations: Volume='"+str(volInt)+"' which is not Vol='"+str(ser.Vol)+"'")
                if numInt != ser.Num:
                    LogError("***Inconsistent serial designations: Number='"+str(numInt)+"' which is not Num='"+str(ser.Num)+"'")

            elif ser.Num is not None:
                if wholeInt is None:
                    wholeInt=ser.Num

                if wholeInt != ser.Num:
                    LogError("***Inconsistent serial designations: Whole='"+str(wholeInt)+"'  which is not Num='"+str(ser.Num)+"'")

            if ser.Whole is not None:
                wholeInt=ser.Whole

            numsuffix=ser.NumSuffix
            wsuffix=ser.WSuffix

    return FanzineSerial(Vol=volInt, Num=numInt, NumSuffix=numsuffix, Whole=wholeInt, WSuffix=wsuffix)


#======================================================================================
def FetchFileFromServer(directoryUrl: str) -> str|None:
    # Download the index.html, which is
    # * The fanzine's Issue Index Table page
    # * A singleton page
    # * The root of a tree with multiple Issue Index Pages
    Log(f"    opening {directoryUrl}", noNewLine=True)
    try:
        h=requests.get(directoryUrl, timeout=1, headers={'Cache-Control': 'no-cache'})
    except:
        LogError(f"\n***FetchFileFromServer failed. Retrying after 1.0 sec: {directoryUrl}")
        time.sleep(0.5)
        try:    # Do first retry
            h=requests.get(directoryUrl, timeout=2, headers={'Cache-Control': 'no-cache'})
        except:
            try:  # Do second retry
                LogError(f"\n***FetchFileFromServer failed again. Retrying after 2.0 sec: {directoryUrl}")
                time.sleep(2.0)
                h=requests.get(directoryUrl, timeout=4, headers={'Cache-Control': 'no-cache'})
            except:
                try:  # Do third retry
                    LogError(f"\n***FetchFileFromServer failed again. Retrying after 5.0 sec: {directoryUrl}")
                    time.sleep(5.0)
                    h=requests.get(directoryUrl, timeout=8, headers={'Cache-Control': 'no-cache'})
                except:
                    LogError(f"\n***FetchFileFromServer failed four times. Load attempt aborted: {directoryUrl}")
                    return None
    Log("...loaded", noNewLine=True)

    # # This kludge is to deal with an ellipses character in "Afterworlds - An Eclectic Bill Bowers Appreciation… and Fanthology…" which for some reason are mishandled
    # txt=h.text.replace("â¦", "...")
    # if txt != h.text:
    #     assert False

    h.encoding='UTF-8'
    x=h.text
    y=x.replace("&uuml;", "ü")
    return y
