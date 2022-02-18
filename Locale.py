from __future__ import annotations

import re

from Log import Log

class Locale:
    def __init__(self, rawtext:str):
        self._rawString=""
        self._country=""
        self._state=""
        self._city=""
        self._weirdo=""
        self.Value=rawtext

    def __str__(self) -> str:
        if self._country != "" or self._state != "" or self._city != "":
            return f"{self._country}: {self._state}: {self._city}"
        if self._weirdo != "":
            return self._weirdo
        return self._rawString

    def __eq__(self, other: Locale) -> bool:
        if self._country != "" or self._state != "" or self._city != "" or self._weirdo != "" or \
                other._country != "" or other._state != "" or other._city != "" or other._weirdo != "":
            return self._country == other._country and self._state == other._state and self._city == other._city and self._weirdo == other._weirdo
        return True

    def __hash__(self):
        if self._country != "" or self._state != "" or self._city != "" or self._weirdo != "":
            return hash(self._country)+hash(self._state)+hash(self._city)+hash(self._weirdo)+hash(self._rawString)
        return hash(self._rawString)


    @property
    # Region is the Locale without the city
    def Region(self) -> str:
        if self._country != "" and self._state != "":
            return f"{self._country}:{self._state}"
        if self._country != "":
            return self._country
        if self._state != "":
            return self._state
        if self._weirdo != "":
            return self._weirdo
        return self._rawString

    @property
    def Country(self) -> str:
        if self._country != "":
            return self._country
        if self._weirdo != "":  # If there's no country, but there is a weirdo, return it.
            return self._weirdo
        return "US"     # Per Joe, default for no country is US


    @property
    def State(self) -> str:
        return self._state

    @property
    def City(self) -> str:
        return self._city

    # .....................
    @property
    def Value(self) -> str:  # FanzineIssueInfo
        return self._rawString
    @Value.setter
    # Inputs can be:
    #   <country>  (e.g., "US", "U.K."
    #   <country>:<city>    (e.g., AU: Melbourne)
    #   <State>:<City>      (e.g., IL:Chicago)
    def Value(self, val: str) -> None:  # FanzineIssueInfo
        if val is None:
            val=""
        val=val.strip().replace("\n", " ")
        self._rawString=val
        if val == "":
            return

        # Sometimes the Locale is just the name of a country
        JustPlainCountries={
                            "Argentina": "Argentina",
                            "Austria": "Austria",
                            "Australia": "Australia",
                            "AUSTRALIA": "Australia",
                            "AUS": "Australia",
                            "AU": "Australia",
                            "Belgium": "Belgium",
                            "Brazil": "Brazil",
                            "Canada": "Canada",
                            "CANADA": "Canada",
                            "Denmark": "Denmark",
                            "France": "France",
                            "Germany": "Germany",
                            "Ireland": "Ireland",
                            "Israel": "Israel",
                            "Japan": "Japan",
                            "Netherlands": "Netherlands",
                            "New Zealand": "NZ",
                            "NZ": "NZ",
                            "Norway": "Norway",
                            "Sweden": "Sweden",
                            "Switzerland": "Switzerland",
                            "Turkey": "Turkey",
                            "UK": "UK",
                            "US": "US"
                            }
        if val in JustPlainCountries.keys():
            self._country=JustPlainCountries[val]
            return

        # Sometimes the Locale is of the form "Country: <country>
        m=re.match("Country:(.+)$", val)
        if m is not None:
            self._country=m.groups()[0].strip()
            return

        states=['AK', 'AL', 'AR', 'AZ', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'GA',
                'HI', 'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME',
                'MI', 'MN', 'MO', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM',
                'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX',
                'UT', 'VA', 'VT', 'WA', 'WI', 'WV', 'WY']
        provinces=['AB', 'BC', 'MB', 'NB', 'NL', 'NS', 'NT', 'NU', 'ON', 'PE', 'QC', 'SK', 'YT']
        provincesDict={
            'Alberta': 'AB',
            'British Columbia': 'BC',
            'Manitoba': 'MB',
            'New Brunswick': 'NB',
            'Newfoundland and Labrador': 'NL',
            'Northwest Territories': 'NT',
            'Nova Scotia': 'NS',
            'Nunavut': 'NU',
            'Ontario': 'ON',
            'Prince Edward Island': 'PE',
            'Quebec': 'QC',
            'Saskatchewan': 'SK',
            'Yukon': 'YT'
        }


        # <Country>:<City> <State>
        # First look to see if it is of the form abc: def XX, where XX is two UC letters.
        m=re.match("([a-zA-Z\s.]{2,99}):([A-Za-z\s.,-]+) ([A-Z]{2})", val)
        if m:
            self._country=m.groups()[0].strip()
            self._state=m.groups()[2].strip()
            self._city=m.groups()[1].strip()
            return

        # XX:abc, where XX is two UC letters.
        # XX might be a state, province or country code
        m=re.match("([A-Z]{2}):([A-Za-z\s.,-]+)", val)
        if m:
            # <Country>: <City>
            # <State>: <City>
            if m.groups()[0] in states:
                self._country="US"
                self._state=m.groups()[0].strip()
                self._city=m.groups()[1].strip()
                return
            elif m.groups()[0] in provinces:
                self._country="CA"
                self._state=m.groups()[0].strip()
                self._city=m.groups()[1].strip()
                return
            else:
                self._country=m.groups()[0].strip()
                self._city=m.groups()[1].strip()
                return

        # Abc XX,  (no colon)
        # XX might be a state, province or country code
        m=re.match("([A-Za-z\s.,-]+)[,\s]([A-Z]{2})", val)
        if m:
            first=m.groups()[0].strip()
            second=m.groups()[1].strip()

            if second in states:
                self._country="US"
                self._state=second
                self._city=first
                return
            elif second in provinces:
                self._country="CA"
                self._state=second
                self._city=first
                return
            elif second in JustPlainCountries.keys():
                self._country=JustPlainCountries[second]
                self._city=first
                return

        # <Country>:<City>
        # Abc:Abc where the first token is a known country
        m=re.match("([A-Za-z\s]+):([A-Za-z\s.,-]+)", val)
        if m:
            first=m.groups()[0].strip()
            second=m.groups()[1].strip()
            if first in JustPlainCountries.keys():
                self._country=JustPlainCountries[first]
                self._city=second
                return
            elif first in states:
                self._country="US"
                self._state=first
                self._city=second
                return
            elif first in provincesDict.keys():
                self._country="CA"
                self._state=provincesDict[first]
                self._city=second
                return

        Log(f"ExtractCountry: Can't interpret {val}", isError=True)
        self._weirdo=val


    STATES_TUPLE=[("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"), ("AR", "Arkansas"), ("CA", "California"), ("CO", "Colorado"),
                  ("CT", "Connecticut"), ("DC", "Washington DC"), ("DE", "Delaware"), ("FL", "Florida"), ("GA", "Georgia"),
                  ("HI", "Hawaii"), ("ID", "Idaho"), ("IL", "Illinois"), ("IN", "Indiana"), ("IA", "Iowa"), ("KS", "Kansas"), ("KY", "Kentucky"),
                  ("LA", "Louisiana"), ("ME", "Maine"), ("MD", "Maryland"), ("MA", "Massachusetts"), ("MI", "Michigan"), ("MN", "Minnesota"),
                  ("MS", "Mississippi"), ("MO", "Missouri"), ("MT", "Montana"), ("NE", "Nebraska"), ("NV", "Nevada"), ("NH", "New Hampshire"),
                  ("NJ", "New Jersey"), ("NM", "New Mexico"), ("NY", "New York"), ("NC", "North Carolina"), ("ND", "North Dakota"), ("OH", "Ohio"),
                  ("OK", "Oklahoma"), ("OR", "Oregon"), ("PA", "Pennsylvania"), ("RI", "Rhode Island"), ("SC", "South Carolina"), ("SD", "South Dakota"),
                  ("TN", "Tennessee"), ("TX", "Texas"), ("UT", "Utah"), ("VT", "Vermont"), ("VA", "Virginia"), ("WA", "Washington"), ("WV", "West Virginia"),
                  ("WI", "Wisconsin"), ("WY", "Wyoming")]


    can_province_names={
        'AB': 'Alberta',
        'BC': 'British Columbia',
        'MB': 'Manitoba',
        'NB': 'New Brunswick',
        'NL': 'Newfoundland and Labrador',
        'NS': 'Nova Scotia',
        'NT': 'Northwest Territories',
        'NU': 'Nunavut',
        'ON': 'Ontario',
        'PE': 'Prince Edward Island',
        'QC': 'Quebec',
        'SK': 'Saskatchewan',
        'YT': 'Yukon'
    }