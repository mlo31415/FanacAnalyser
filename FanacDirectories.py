from bs4 import BeautifulSoup
import requests
import Helpers


# ===============================================================================
# This is a class to manage the list of fanzine directories in fanac.org
# It creates a list of all the directors listed under classic or modern fanzines
# It reads it from the website, not from a local copy.

global g_FanacDirectories   # This is global to share a single instance of the data among all instances of the class, *not* to allow access except through class members
g_FanacDirectories={}

class FanacDirectories:

    def __init__(self):
        global g_FanacDirectories
        if len(g_FanacDirectories) == 0:
            self.ReadClassicModernPages()

    def Dict(self):
        return g_FanacDirectories

    # -------------------------------------------------------------------------
    # We have a name and a dirname from the fanac.org Classic and Modern pages.
    # The dirname *might* be a URL in which case it needs to be handled as a foreign directory reference
    def AddDirectory(self, name, dirname):
        isDup=False

        if name in g_FanacDirectories:
            print("   duplicate: name="+name+"  dirname="+dirname)
            return

        if dirname[:3]=="http":
            print("    ignored, because is HTML: "+dirname)
            return

        # Add name and directory reference\
        cname=Helpers.CompressName(name)
        print("   added to fanacDirectories: key='"+cname+"'  name='"+name+"'  dirname='"+dirname+"'")
        g_FanacDirectories[cname]=(name, dirname)
        return

    def Contains(self, name):
        return Helpers.CompressName(name) in g_FanacDirectories

    def GetTuple(self, name):
        if self.Contains(name):
            return g_FanacDirectories[Helpers.CompressName(name)]
        if self.Contains(name+"the"):
            return g_FanacDirectories[Helpers.CompressName(name+"the")]
        if self.Contains(name+"an"):
            return g_FanacDirectories[Helpers.CompressName(name+"an")]
        if self.Contains(name+"a"):
            return g_FanacDirectories[Helpers.CompressName(name+"a")]
        return None

    def len(self):
        return len(g_FanacDirectories)

    # ====================================================================================
    # Read fanac.org/fanzines/Classic_Fanzines.html amd /Modern_Fanzines.html
    # Read the table to get a list of all the fanzines on Fanac.org
    # Return a list of tuples (name on page, name of directory)
    #       The name on page is the display named used in the Classic and Modern tables
    #       The name of directory is the name of the directory pointed to

    def ReadClassicModernPages(self):
        fanzinesList=[]
        print("----Begin reading Classic and Modern tables")

        self.ReadModernOrClassicTable("http://www.fanac.org/fanzines/Classic_Fanzines.html")
        self.ReadModernOrClassicTable("http://www.fanac.org/fanzines/Modern_Fanzines.html")

        print("----Done reading Classic and Modern tables")
        return

    # ======================================================================
    def ReadModernOrClassicTable(self, url):
        h=requests.get(url)
        s=BeautifulSoup(h.content, "html.parser")
        # We look for the first table that does ot contain a "navbar"
        tables=s.body.find_all("table")
        for table in tables:
            if "sortable" in str(table.attrs) and not "navbar" in str(table.attrs):
                # OK, we've found the main table.  Now read it
                trs=table.find_all("tr")
                for i in range(1, len(trs)):
                    # Now the data rows
                    name=trs[i].find_all("td")[1].contents[0].contents[0].contents[0]
                    dirname=trs[i].find_all("td")[1].contents[0].attrs["href"][:-1]
                    self.AddDirectory(name, dirname)
        return

# End of class FanacDirectories