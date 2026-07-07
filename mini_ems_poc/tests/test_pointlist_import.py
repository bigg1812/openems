import base64
import io
import unittest
import zipfile

from mini_ems_poc.mini_ems_runtime.bacnet_discovery import preview_bacnet_discovery_payload
from mini_ems_poc.mini_ems_runtime.pointlist_import import import_pointlist_payload


class PointlistImportTest(unittest.TestCase):
    def test_imports_csv_pointlist_as_mapping_candidates(self) -> None:
        content = "\n".join(
            [
                "Object Reference;Name;Unit;Value;Mini EMS Kanal",
                "/100.AV300;Netzleistung;kW;42,3;grid.active_power_kw",
                "/100.AI1801;Außentemperatur;°C;8.4;site.outdoor_temperature_c",
            ]
        )

        result = import_pointlist_payload(
            {
                "filename": "datenpunkte.csv",
                "content": content,
                "default_device": {"host": "192.168.244.10", "port": 47808},
            }
        )

        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(len(result["raw_points"]), 2)
        self.assertEqual(result["raw_points"][0]["id"], "bacnet:device_100:av:300")
        self.assertEqual(result["raw_points"][0]["name"], "Netzleistung")
        self.assertEqual(result["candidates"][0]["value"], 42.3)
        self.assertEqual(result["mapping_draft"]["mappings"][0]["channel_id"], "grid.active_power_kw")

    def test_imports_xlsx_pointlist_without_runtime_dependency(self) -> None:
        result = import_pointlist_payload(
            {
                "filename": "datenpunkte.xlsx",
                "content_base64": base64.b64encode(_xlsx_bytes()).decode("ascii"),
            }
        )

        self.assertTrue(result["valid"])
        self.assertEqual(len(result["raw_points"]), 2)
        self.assertEqual(result["raw_points"][1]["object_type"], "bv")
        self.assertEqual(result["raw_points"][1]["instance"], 401)
        self.assertEqual(result["candidates"][1]["access"], "write")

    def test_unsupported_objects_remain_candidates_but_not_active_raw_points(self) -> None:
        content = "Object Reference;Name;Access\n/100.BO12;Kessel Freigabe;write\n"

        result = import_pointlist_payload({"filename": "datenpunkte.csv", "content": content})

        self.assertTrue(result["valid"])
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["object_type"], "bo")
        self.assertEqual(result["raw_points"], [])
        self.assertIn("noch kein aktivierbarer", " / ".join(result["warnings"]))


class BacnetDiscoveryPreviewTest(unittest.TestCase):
    def test_discovery_uses_only_read_methods_and_returns_candidates(self) -> None:
        app = FakeDiscoveryApplication()

        result = preview_bacnet_discovery_payload(
            {"low_limit": 100, "high_limit": 100, "max_objects_per_device": 8},
            application=app,
        )

        self.assertTrue(result["valid"])
        self.assertTrue(result["source"]["read_only"])
        self.assertEqual(len(result["raw_points"]), 2)
        self.assertEqual(result["raw_points"][0]["id"], "bacnet:device_100:av:300")
        self.assertEqual(result["raw_points"][1]["id"], "bacnet:device_100:ai:1801")
        self.assertEqual(app.write_calls, [])
        self.assertTrue(app.closed)


class IAm:
    pduSource = "192.168.244.10"
    iAmDeviceIdentifier = ("device", 100)


class FakeDiscoveryApplication:
    def __init__(self) -> None:
        self.write_calls = []
        self.closed = False

    async def who_is(self, low_limit, high_limit):
        self.low_limit = low_limit
        self.high_limit = high_limit
        return [IAm()]

    async def read_property(self, address, object_identifier, property_identifier, array_index=None):
        if property_identifier == "object-list":
            return [("analog-value", 300), ("analog-input", 1801), ("binary-output", 12)]
        values = {
            (("analog-value", 300), "object-name"): "Netzleistung",
            (("analog-value", 300), "present-value"): 42.3,
            (("analog-value", 300), "units"): "kW",
            (("analog-input", 1801), "object-name"): "Außentemperatur",
            (("analog-input", 1801), "present-value"): 8.4,
            (("analog-input", 1801), "units"): "°C",
        }
        return values.get((object_identifier, property_identifier))

    def write_property(self, *args, **kwargs):
        self.write_calls.append((args, kwargs))

    def close(self):
        self.closed = True


def _xlsx_bytes() -> bytes:
    rows = [
        ["Object Reference", "Name", "Unit", "Value", "Access"],
        ["/100.AI1801", "Außentemperatur", "°C", "8.4", "read"],
        ["/100.BV401", "Spotmarkt Sperre", "", "", "write"],
    ]
    shared_strings = []
    string_index = {}

    def shared(value):
        text = str(value)
        if text not in string_index:
            string_index[text] = len(shared_strings)
            shared_strings.append(text)
        return string_index[text]

    sheet_rows = []
    for row_number, row in enumerate(rows, start=1):
        cells = []
        for column_number, value in enumerate(row, start=1):
            cell_ref = "{0}{1}".format(_column_name(column_number), row_number)
            cells.append('<c r="{0}" t="s"><v>{1}</v></c>'.format(cell_ref, shared(value)))
        sheet_rows.append('<row r="{0}">{1}</row>'.format(row_number, "".join(cells)))

    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        + "".join("<si><t>{0}</t></si>".format(value) for value in shared_strings)
        + "</sst>"
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        + "".join(sheet_rows)
        + "</sheetData></worksheet>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as workbook:
        workbook.writestr("xl/sharedStrings.xml", shared_xml)
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return output.getvalue()


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name


if __name__ == "__main__":
    unittest.main()
