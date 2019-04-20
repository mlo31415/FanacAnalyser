import os
import re
from bs4 import NavigableString
import urllib
import roman


#-------------------------------------------------------------
def CannonicizeColumnHeaders(header):
    # 2nd item is the cannonical form
    translationTable={
                        "published" : "date",
                        "editors" : "editor",
                        "zine" : "issue",
                        "fanzine" : "issue",
                        "mo." : "month",
                        "mon" : "month",
                        "quartermonth" : "month",
                        "quarter" : "month",
                        "season" : "month",
                        "notes" : "notes",
                        "no." : "number",
                        "no,": "number",
                        "num" : "number",
                        "#" : "number",
                        "page" : "pages",
                        "pages" : "pages",
                        "pp," : "pages",
                        "pub" : "publisher",
                        "vol" : "volume",
                        "volume" : "volume",
                        "volumenumber" : "volnum",
                        "vol#" : "volnum",
                        "vol.#" : "volnum",
                        "wholenum" : "whole",
                        "year" : "year",
                      }
    try:
        return translationTable[header.replace(" ", "").replace("/", "").lower()]
    except:
        return header.lower()


#-----------------------------------------
# Find text bracketed by <b>...</b>
# Return the contents of the first pair of brackets found and the remainder of the input string
def FindBracketedText(s, b):
    strlower=s.lower()
    l1=strlower.find("<"+b.lower())
    if l1 == -1:
        return "", ""
    l1=strlower.find(">", l1)
    if l1 == -1:
        Log("***Error: no terminating '>' found in "+strlower+"'", True)
        return "", ""
    l2=strlower.find("</"+b.lower()+">", l1+1)
    if l2 == -1:
        return "", ""
    return s[l1+1:l2], s[l2+3+len(b):]


#=====================================================================================
# Function to pull and href and accompanying text from a Tag
# The structure is "<a href='URL'>LINKTEXT</a>
# We want to extract the URL and LINKTEXT
def GetHrefAndTextFromTag(tag):
    try:
        href=tag.contents[0].attrs.get("href", None)
    except:
        try:
            href=tag.attrs.get("href")
        except:
            return tag, None

    return tag.contents[0].string, href


#=====================================================================================
# Remove certain strings which amount to whitespace
def RemoveHTMLDebris(s: str):
    return s.replace("<br>", "").replace("<BR>", "")


#=====================================================================================
# Function to generate the proper kind of path.  (This may change depending on the target location of the output.)
def RelPathToURL(relPath: str):
    if relPath is None:
        return None
    if relPath.startswith("http"):  # We don't want to mess with foreign URLs
        return None
    return "http://www.fanac.org/"+os.path.normpath(os.path.join("fanzines", relPath)).replace("\\", "/")


#=====================================================================================
# Simple function to name tags for debugging purposes
def N(tag):
    try:
        return tag.__class__.__name__
    except:
        return "Something"


#=====================================================================================
# Function to compress newline elements from a list of Tags.
def RemoveNewlineRows(tags):
    compressedTags = []
    for row in tags:
        if not isinstance(row, NavigableString):
            compressedTags.append(row)
    return compressedTags


#=====================================================================================
# Function to find the index of a string in a list of strings
def FindIndexOfStringInList(lst: list, s: str):
    try:
        return lst.index(s)
    except:
        return None

#=====================================================================================
# Function to search recursively for the table containing the fanzines listing
# flags is a dictionary of attributes and values to be matched, e.g., {"class" : "indextable", ...}
# We must match all of them
def LookForTable(soup, flags):

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


#==================================================================================
def CreateFanacOrgAbsolutePath(fanacDir: str, s: str):
    return "http://www.fanac.org/fanzines/"+fanacDir+"/"+s


#==================================================================================
# Return a properly formatted link
def FormatLink(name: str, url: str):
    # TODO: Do we need to deal with turning blanks into %20 whatsits?
    return '<a href='+url+'>'+name+'</a>'


#==================================================================================
# Create a name for comparison purposes which is lower case and without whitespace or punctuation
# We make it all lower case
# We move leading "The ", "A " and "An " to the rear
# We remove spaces and certain punctuation
def CompressName(name):
    name=name.lower()
    if name.startswith("the "):
        name=name[:4]+"the"
    if name.startswith("a "):
        name=name[:2]+"a"
    if name.startswith("an "):
        name=name[:3]+"an"
    return name.replace(" ", "").replace(",", "").replace("-", "").replace("'", "").replace(".", "").replace("’", "")


#==================================================================================
def CompareCompressedName(n1, n2):
    return CompressName(n1) == CompressName(n2)




#=============================================================================
# Print the text to a log file open by the main program
# If isError is set also print it to the error file.
def Log(text: str, isError=False):
    global g_logFile
    global g_errorFile
    global g_logHeader
    global g_logErrorHeader

    # If this is the first log entry for this header, print it and then clear it so it's not printed again
    if g_logHeader is not None:
        print(g_logHeader)
        print("\n"+g_logHeader, file=g_logFile)
    g_logHeader=None

    if isError:
        # If this and error entry and is the first error entry for this header, print the header and then clear it so it's not printed again
        if g_logErrorHeader is not None:
            print("----\n"+g_logErrorHeader, file=g_errorFile)
        g_logErrorHeader=None

    # Print the log entry itself
    print(text)
    print(text, file=g_logFile)
    if isError:
        print(text, file=g_errorFile)

# Set the header for any subsequent log entries
# Note that this header will only be printed once, and then only if there has been a log entry
def LogSetFanzine(name: str):
    global g_logHeader
    global g_logErrorHeader
    global g_logLastFanzine

    if g_logLastFanzine is None or name != g_logLastFanzine:
        g_logHeader=name
        g_logErrorHeader=name
        g_logLastFanzine=name


def LogOpen(logfilename: str, errorfilename: str):
    global g_logFile
    g_logFile=open(logfilename, "w+")

    global g_errorFile
    g_errorFile=open(errorfilename, "w+")

    global g_logHeader
    g_logHeader=None
    global g_logErrorHeader
    g_logErrorHeader=None
    global g_logLastFanzine
    g_logLastFanzine=None


def LogClose():
    global g_logFile
    g_logFile.close()
    global g_errorFile
    g_errorFile.close()


def LogFailureAndRaiseIfMissing(fname: str):
    if not os.path.exists(fname):
        Log("Fatal error: Can't find "+fname, isError=True)
        raise FileNotFoundError

# =============================================================================
#   Change the filename in a URL
def ChangeFileInURL(url: str, newFileName: str):
    u=urllib.parse.urlparse(url)
    p=u[2].split("/")   # Split the path (which may include a filename) into components
    f=p[-1:][0].split(".")     # Split the last component of the path (which may be a filename) into stuff plus an extension
    if len(f) > 1:
        # If there is an extension, then the last component of the path is a filename to be replaced.
        p="/".join(p[:-1])+"/"+newFileName
    else:
        # Otherwise, we just tack on the new filename
        p="/".join(p)+"/"+newFileName

    u=(u[0], u[1], p, u[3], u[4], u[5])
    return urllib.parse.urlunparse(u)


# =============================================================================
# Check to see if an argument (int, float or string) is a number
def IsInt(arg):
    if type(arg) is int:
        return True

    # It's not an integer type.  See if it can be converted into an integer.  E.g., it's a string representation of a number
    try:
        x=int(arg)  # We throw away the result -- all we're interested in is if the conversation can be done without throwing an error
        return True
    except:
        return False


# =============================================================================
# Check to see if an argument (int, float or string) is a number
def IsNumeric(arg):
    if type(arg) in [float, int]:
        return True

    # It's not a numeric type.  See if it can be converted into a float.  E.g., it's a string representation of a number
    try:
        x=float(arg)    # We throw away the result -- all we're interested in is if the conversation can be done without throwing an error
        return True
    except:
        return False



# =============================================================================
# Read a list of lines in from a file
# Strip leading and trailing whitespace and ignore lines which begin with a '#'
def ReadList(filename: str, isFatal=False):
    if not os.path.exists(filename):
        if isFatal:
            Log("Fatal error: Can't find "+filename, isError=True)
            raise FileNotFoundError
        print("ReadList can't open "+filename)
        return None
    f=open(filename, "r")
    lst=f.readlines()
    f.close()

    lst=[l.strip() for l in lst]  # Strip leading and trailing whitespace
    lst=[l for l in lst if len(l)>0 and l[0]!= "#"]   # Drop empty lines and lines starting with "#"

    lst=[l for l in lst if l.find(" #") == -1] + [l[:l.find(" #")].strip() for l in lst if l.find(" #") > 0]    # (all members not containing " #") +(the rest with the trailing # stripped)

    return lst


# =============================================================================
# Try to interpret a string as an integer
#   nnn
#   nnn-nnn
#   nnn.nnn
#   nnnaaa
def InterpretNumber(inputstring: str):
    value=None
    if inputstring is not None:
        inputstring=inputstring.strip()
        if IsInt(inputstring):  # Simple integer
            value=int(inputstring)
        if value is None:
            # nn-nn (Hyphenated integers which usually means a range of numbers)
            p=re.compile("^([0-9]+)-([0-9]+)$")  # nnn + dash + nnn
            m=p.match(inputstring)
            if m is not None and len(m.groups()) == 2:
                value=int(m.groups()[0])        # We just sorta ignore n2...
        if value is None:
            # nn.nn (Decimal number)
            p=re.compile("^([0-9]+.[0-9]+)$")   # nnn.nnn
            m=p.match(inputstring)
            if m is not None and len(m.groups()) == 1:
                value=float(m.groups()[0])      # Note that this returns a float
        if value is None:
            # nnaa (integer followed by letter)
            p=re.compile("^([0-9]+)\s?([a-zA-Z]+)$")  # nnn + optional space + nnn
            m=p.match(inputstring)
            if m is not None and len(m.groups()) == 2:
                value=int(m.groups()[0])
        if value is None:
            p=re.compile("^([IVXLC]+)$")        # roman numeral characters
            m=p.match(inputstring)
            if m is not None and len(m.groups()) == 1:
                value=roman.fromRoman(m.groups()[0])
        if value is None:
            if inputstring is not None and len(inputstring) > 0:
                Log("*** Uninterpretable number: '"+str(inputstring)+"'", True)
    return value