# -*- conding: utf-8 -*-
from flask import Flask, render_template, request, Response
import requests
import json
import sqlite3

CONN = sqlite3.connect("us_zip.db", check_same_thread=False)


class Inventory:
    def __init__(self):
        self._data = {}

    def check_site_for_item(self, item, fsl):
        site_inv = self._data.get(fsl, [])
        for inv_item, qty in site_inv:
            if inv_item == item:
                return True
        return False


FAKE_INVENTORY = Inventory()
FAKE_INVENTORY._data = {'LAX-005': [('CISCO2811', 10), ('FAKEITEM', 3)],
                        'LGA-003': [('CISCO2811', 10), ('FAKEITEM', 3)],
                        'MSY-001': [('CISCO2811', 10), ('FAKEITEM', 3)],
                        'MIA-002': [('CISCO2811', 10), ('FAKEITEM', 3)]
                        }


class NoResultsFound(Exception):
    pass


def get_lat_lng_from_zip(zip_code, country_code=None):
    # country_code is expected to be upper

    curs = CONN.cursor()

    if country_code:
        country_code = country_code.upper()
        curs.execute("""SELECT
                            cc, postal, lat, lng
                        FROM
                            us_zip_code
                        WHERE
                            cc = ?
                        AND postal = ?""", (country_code, zip_code))
    else:
        curs.execute("""SELECT
                            cc, postal, lat, lng
                        FROM
                            us_zip_code
                        WHERE
                            postal = ? """, (zip_code,))

    return curs.fetchall()


# Misc Support Functions
class JSONResponse(Response):
    def __init__(self, obj):
        Response.__init__(self, json.dumps(obj, indent=4, separators=(',', ': ')),
                          mimetype="application/json")


class ZipCodeSearch:
    def __init__(self, item, zipcode, country_code, inventory):
        self.item = item
        self.zipcode = zipcode
        self.country_code = country_code
        self.lat, self.lng = None, None
        self._search_zip_db()
        self.fsls = self._get_nearest_fsls()
        self._search_inventory(inventory)

    def _search_zip_db(self):
        results = get_lat_lng_from_zip(self.zipcode, self.country_code)

        if not results:
            raise NoResultsFound

        cc, postal, lat, lng = results[0]
        self.lat, self.lng = lat, lng
        if not self.country_code:
            self.country_code = cc

    def _get_nearest_fsls(self):
        # API requires country_code to be upper
        url = "http://nhrapps.appspot.com/get_sites"
        data = {'lat': str(self.lat), 'lng': str(self.lng), 'country_code': self.country_code.upper()}
        r = requests.get(url, params=data)
        r_json = r.json()
        # should check status_code
        if r_json[0]['status'] == 'error':
            return []
        else:
            return r_json

    def _search_inventory(self, inv_obj):
        for fsl in self.fsls:
            fsl['has_inventory'] = inv_obj.check_site_for_item(self.item, fsl['name'])

    def get_lat_lng(self):
        return self.lat, self.lng


app = Flask(__name__)


@app.route('/')
def index():
    try:
        return render_template("index.html")
    except Exception, e:
        print e
        return """<strong style ="color:red;">Error - Zoinks!!</strong>"""


@app.route('/_get_fsl', methods=['GET'])
def _get_fsl():
    item = request.values.get('item')
    zipcode = request.values.get('zipcode')
    country_code = request.values.get('country_code')

    try:
        data = ZipCodeSearch(item, zipcode, country_code.upper(), FAKE_INVENTORY)
        data = data.fsls
    except NoResultsFound:
        data = {'error': 'NoResultsFound'}

    return JSONResponse(data)


if __name__ == '__main__':
    app.run(debug=True)
