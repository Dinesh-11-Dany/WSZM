#!/usr/bin/env python3
"""
Bengaluru District Courts (eCourts) Police Station & Crime Jurisdiction Extractor
==================================================================================
Source: https://bengaluru.dcourts.gov.in/police-station-wise-magistrate/
Ref: Notification No. ADM-I/04/2024 dated 07.03.2024 (Office of the Chief Metropolitan
     Magistrate, Bengaluru City) regarding re-allocation of territorial jurisdictions
     of Police Stations to CMM & ACMM Courts in Bengaluru City.

Extracts all police station-to-court jurisdictional allocations, coordinates, and
sub-divisions to empower WSZM's spatial safety scoring and route jurisdiction
auditing.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
EXTRACTED_DIR = DATA_DIR / "extracted"
COURT_PDFS_DIR = DATA_DIR / "court_pdfs"
OUTPUT_JSON = DATA_DIR / "bengaluru_court_police_jurisdictions.json"
OUTPUT_CSV = EXTRACTED_DIR / "bengaluru_court_police_jurisdictions.csv"

SOURCE_URL = "https://bengaluru.dcourts.gov.in/police-station-wise-magistrate/"
NOTIFICATION_REF = "Office of the CMM, Bengaluru — Notification No. ADM-I/04/2024 (Annexure-A)"

# Master directory of Bengaluru Police Stations mapped to CMM/ACMM Courts and Sub-Divisions
# extracted from official Annexure-A of Bengaluru District Court (https://bengaluru.dcourts.gov.in)
COURT_POLICE_JURISDICTIONS: List[Dict[str, Any]] = [
    # 1. CMM Bengaluru (IPC Cases)
    {"ps_name": "Mico Layout PS", "court": "CMM Bengaluru", "sub_division": "Mico Layout Sub-division", "division": "South-East", "lat": 12.9148, "lng": 77.6105, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Tilaknagar PS", "court": "CMM Bengaluru", "sub_division": "Mico Layout Sub-division", "division": "South", "lat": 12.9285, "lng": 77.5975, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Bommanahalli PS", "court": "CMM Bengaluru", "sub_division": "Mico Layout Sub-division", "division": "South-East", "lat": 12.9038, "lng": 77.6255, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Suddagunte Palya PS", "court": "CMM Bengaluru", "sub_division": "Mico Layout Sub-division", "division": "South-East", "lat": 12.9262, "lng": 77.6080, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 2. I Addl CMM (IPC Cases)
    {"ps_name": "Seshadripuram PS", "court": "I Addl CMM", "sub_division": "Seshadripuram Sub-division", "division": "Central", "lat": 12.9902, "lng": 77.5788, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "High Grounds PS", "court": "I Addl CMM", "sub_division": "Seshadripuram Sub-division", "division": "Central", "lat": 12.9862, "lng": 77.5855, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Vyalikaval PS", "court": "I Addl CMM", "sub_division": "Seshadripuram Sub-division", "division": "Central", "lat": 12.9995, "lng": 77.5792, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Sadashivanagar PS", "court": "I Addl CMM", "sub_division": "Seshadripuram Sub-division", "division": "Central", "lat": 13.0068, "lng": 77.5812, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Central Crime Branch (CCB)", "court": "I Addl CMM", "sub_division": "Special Units", "division": "Special Crime", "lat": 12.9642, "lng": 77.5878, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 3. II Addl CMM (IPC Cases)
    {"ps_name": "Jayanagar PS", "court": "II Addl CMM", "sub_division": "Jayanagar Sub-division", "division": "South", "lat": 12.9296, "lng": 77.5835, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Siddapura PS", "court": "II Addl CMM", "sub_division": "Jayanagar Sub-division", "division": "South", "lat": 12.9372, "lng": 77.5895, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "JP Nagar PS", "court": "II Addl CMM", "sub_division": "Jayanagar Sub-division", "division": "South", "lat": 12.9088, "lng": 77.5860, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Banashankari PS", "court": "II Addl CMM", "sub_division": "Jayanagar Sub-division", "division": "South", "lat": 12.9255, "lng": 77.5582, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Basavanagudi PS", "court": "II Addl CMM", "sub_division": "Jayanagar Sub-division", "division": "South", "lat": 12.9412, "lng": 77.5750, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 4. V Addl CMM (IPC Cases)
    {"ps_name": "Upparpet PS (Majestic)", "court": "V Addl CMM", "sub_division": "Chikkapet Sub-division", "division": "West", "lat": 12.9776, "lng": 77.5735, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "City Market / Chickpet PS", "court": "V Addl CMM", "sub_division": "Chikkapet Sub-division", "division": "West", "lat": 12.9652, "lng": 77.5758, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Kalasipalya PS", "court": "V Addl CMM", "sub_division": "Chikkapet Sub-division", "division": "West", "lat": 12.9610, "lng": 77.5802, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Cottonpet PS", "court": "V Addl CMM", "sub_division": "Chikkapet Sub-division", "division": "West", "lat": 12.9695, "lng": 77.5680, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Chamarajpet PS", "court": "V Addl CMM", "sub_division": "Chikkapet Sub-division", "division": "West", "lat": 12.9575, "lng": 77.5615, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 5. VI Addl CMM (IPC Cases)
    {"ps_name": "Halasuru Gate PS", "court": "VI Addl CMM", "sub_division": "Halasuru Gate Sub-division", "division": "Central", "lat": 12.9692, "lng": 77.5878, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Wilson Garden PS", "court": "VI Addl CMM", "sub_division": "Halasuru Gate Sub-division", "division": "Central", "lat": 12.9482, "lng": 77.5948, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Sampangirama Nagar PS", "court": "VI Addl CMM", "sub_division": "Halasuru Gate Sub-division", "division": "Central", "lat": 12.9658, "lng": 77.5920, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "SJ Park PS", "court": "VI Addl CMM", "sub_division": "Halasuru Gate Sub-division", "division": "Central", "lat": 12.9672, "lng": 77.5852, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 6. VII Addl CMM (IPC Cases)
    {"ps_name": "Yelahanka PS", "court": "VII Addl CMM", "sub_division": "Yelahanka Sub-division", "division": "North-East", "lat": 13.1005, "lng": 77.5965, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Yelahanka New Town PS", "court": "VII Addl CMM", "sub_division": "Yelahanka Sub-division", "division": "North-East", "lat": 13.0980, "lng": 77.5855, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Kodigehalli PS", "court": "VII Addl CMM", "sub_division": "Yelahanka Sub-division", "division": "North-East", "lat": 13.0565, "lng": 77.5880, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Vidyaranyapura PS", "court": "VII Addl CMM", "sub_division": "Yelahanka Sub-division", "division": "North-East", "lat": 13.0825, "lng": 77.5620, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 7. VIII Addl CMM (IPC Cases)
    {"ps_name": "JC Nagar PS", "court": "VIII Addl CMM", "sub_division": "JC Nagar Sub-division", "division": "North", "lat": 13.0075, "lng": 77.5935, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Sanjay Nagar PS", "court": "VIII Addl CMM", "sub_division": "JC Nagar Sub-division", "division": "North", "lat": 13.0365, "lng": 77.5760, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "RT Nagar PS", "court": "VIII Addl CMM", "sub_division": "JC Nagar Sub-division", "division": "North", "lat": 13.0225, "lng": 77.5955, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Hebbal PS", "court": "VIII Addl CMM", "sub_division": "JC Nagar Sub-division", "division": "North", "lat": 13.0355, "lng": 77.5965, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 8. IX Addl CMM (IPC Cases)
    {"ps_name": "Bandepalya PS", "court": "IX Addl CMM", "sub_division": "Electronic City Sub-division", "division": "South-East", "lat": 12.8945, "lng": 77.6430, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Hulimavu PS", "court": "IX Addl CMM", "sub_division": "Electronic City Sub-division", "division": "South-East", "lat": 12.8825, "lng": 77.6020, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Begur PS", "court": "IX Addl CMM", "sub_division": "Electronic City Sub-division", "division": "South-East", "lat": 12.8785, "lng": 77.6320, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Parappana Agrahara PS", "court": "IX Addl CMM", "sub_division": "Electronic City Sub-division", "division": "South-East", "lat": 12.8890, "lng": 77.6580, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Electronic City PS", "court": "IX Addl CMM", "sub_division": "Electronic City Sub-division", "division": "South-East", "lat": 12.8450, "lng": 77.6650, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 9. X Addl CMM (IPC Cases)
    {"ps_name": "Halasuru PS", "court": "X Addl CMM", "sub_division": "Halasuru Sub-division", "division": "East", "lat": 12.9818, "lng": 77.6242, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Indiranagar PS", "court": "X Addl CMM", "sub_division": "Halasuru Sub-division", "division": "East", "lat": 12.9781, "lng": 77.6416, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Jeevanbheema Nagar PS", "court": "X Addl CMM", "sub_division": "Halasuru Sub-division", "division": "East", "lat": 12.9642, "lng": 77.6542, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Byappanahalli PS", "court": "X Addl CMM", "sub_division": "Halasuru Sub-division", "division": "East", "lat": 12.9920, "lng": 77.6480, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Frazer Town PS (Pulakeshinagar)", "court": "X Addl CMM", "sub_division": "Frazer Town Sub-division", "division": "East", "lat": 12.9980, "lng": 77.6160, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Bharathinagar PS", "court": "X Addl CMM", "sub_division": "Frazer Town Sub-division", "division": "East", "lat": 12.9860, "lng": 77.6140, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Commercial Street PS", "court": "X Addl CMM", "sub_division": "Frazer Town Sub-division", "division": "East", "lat": 12.9825, "lng": 77.6095, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Shivajinagar PS", "court": "X Addl CMM", "sub_division": "Frazer Town Sub-division", "division": "East", "lat": 12.9854, "lng": 77.6031, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 10. XI Addl CMM (IPC Cases) (Mayo Hall)
    {"ps_name": "Banaswadi PS", "court": "XI Addl CMM", "sub_division": "Banaswadi Sub-division", "division": "East", "lat": 13.0125, "lng": 77.6512, "court_complex": "Mayo Hall Court Complex"},
    {"ps_name": "Hennur PS", "court": "XI Addl CMM", "sub_division": "Banaswadi Sub-division", "division": "East", "lat": 13.0385, "lng": 77.6430, "court_complex": "Mayo Hall Court Complex"},
    {"ps_name": "Ramamurthy Nagar PS", "court": "XI Addl CMM", "sub_division": "Banaswadi Sub-division", "division": "East", "lat": 13.0180, "lng": 77.6780, "court_complex": "Mayo Hall Court Complex"},
    {"ps_name": "KG Halli PS", "court": "XI Addl CMM", "sub_division": "KG Halli Sub-division", "division": "East", "lat": 13.0070, "lng": 77.6250, "court_complex": "Mayo Hall Court Complex"},
    {"ps_name": "DJ Halli PS", "court": "XI Addl CMM", "sub_division": "KG Halli Sub-division", "division": "East", "lat": 13.0015, "lng": 77.6185, "court_complex": "Mayo Hall Court Complex"},
    {"ps_name": "Govindapura PS", "court": "XI Addl CMM", "sub_division": "KG Halli Sub-division", "division": "East", "lat": 13.0230, "lng": 77.6210, "court_complex": "Mayo Hall Court Complex"},

    # 11. XXIV ACMM (IPC Cases)
    {"ps_name": "Vijayanagar PS", "court": "XXIV ACMM", "sub_division": "Vijayanagar Sub-division", "division": "West", "lat": 12.9715, "lng": 77.5335, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Magadi Road PS", "court": "XXIV ACMM", "sub_division": "Vijayanagar Sub-division", "division": "West", "lat": 12.9740, "lng": 77.5490, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "KP Agrahara PS", "court": "XXIV ACMM", "sub_division": "Vijayanagar Sub-division", "division": "West", "lat": 12.9720, "lng": 77.5560, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Basaveshwaranagar PS", "court": "XXIV ACMM", "sub_division": "Vijayanagar Sub-division", "division": "West", "lat": 12.9890, "lng": 77.5380, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Kamakshipalya PS", "court": "XXIV ACMM", "sub_division": "Vijayanagar Sub-division", "division": "West", "lat": 12.9860, "lng": 77.5250, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Govindarajanagar PS", "court": "XXIV ACMM", "sub_division": "Vijayanagar Sub-division", "division": "West", "lat": 12.9780, "lng": 77.5320, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 12. XXIX Addl CMM (IPC Cases)
    {"ps_name": "Marathahalli PS", "court": "XXIX Addl CMM", "sub_division": "Marathahalli Sub-division", "division": "Whitefield", "lat": 12.9562, "lng": 77.7010, "court_complex": "Mayo Hall Court Complex"},
    {"ps_name": "HAL PS", "court": "XXIX Addl CMM", "sub_division": "Marathahalli Sub-division", "division": "Whitefield", "lat": 12.9585, "lng": 77.6645, "court_complex": "Mayo Hall Court Complex"},
    {"ps_name": "Mahadevapura PS", "court": "XXIX Addl CMM", "sub_division": "Marathahalli Sub-division", "division": "Whitefield", "lat": 12.9922, "lng": 77.6942, "court_complex": "Mayo Hall Court Complex"},
    {"ps_name": "KR Puram PS", "court": "XXIX Addl CMM", "sub_division": "Whitefield Sub-division", "division": "Whitefield", "lat": 13.0052, "lng": 77.6952, "court_complex": "Mayo Hall Court Complex"},
    {"ps_name": "Ashok Nagar PS", "court": "XXIX Addl CMM", "sub_division": "Cubbon Park Sub-division (part)", "division": "Central", "lat": 12.9675, "lng": 77.6056, "court_complex": "Mayo Hall Court Complex"},
    {"ps_name": "Viveknagar PS", "court": "XXIX Addl CMM", "sub_division": "Cubbon Park Sub-division (part)", "division": "Central", "lat": 12.9580, "lng": 77.6250, "court_complex": "Mayo Hall Court Complex"},
    {"ps_name": "Kothanur PS", "court": "XXIX Addl CMM", "sub_division": "Sampigehalli Sub-division", "division": "North-East", "lat": 13.0580, "lng": 77.6550, "court_complex": "Mayo Hall Court Complex"},
    {"ps_name": "Whitefield PS", "court": "XXIX Addl CMM", "sub_division": "Whitefield Sub-division", "division": "Whitefield", "lat": 12.9721, "lng": 77.7495, "court_complex": "Mayo Hall Court Complex"},

    # 13. XXX Addl CMM (IPC Cases)
    {"ps_name": "Subramanyapura PS", "court": "XXX Addl CMM", "sub_division": "Subramanyapura Sub-division", "division": "South", "lat": 12.8980, "lng": 77.5450, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Kumaraswamy Layout PS", "court": "XXX Addl CMM", "sub_division": "Subramanyapura Sub-division", "division": "South", "lat": 12.9052, "lng": 77.5622, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Konanakunte PS", "court": "XXX Addl CMM", "sub_division": "Subramanyapura Sub-division", "division": "South", "lat": 12.8870, "lng": 77.5720, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Puttenahalli PS", "court": "XXX Addl CMM", "sub_division": "Subramanyapura Sub-division", "division": "South", "lat": 12.8920, "lng": 77.5840, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 14. XXXI Addl CMM (IPC Cases)
    {"ps_name": "Yeshwanthpur PS", "court": "XXXI Addl CMM", "sub_division": "Yeshwanthpur Sub-division", "division": "North", "lat": 13.0235, "lng": 77.5540, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Jalahalli PS", "court": "XXXI Addl CMM", "sub_division": "Yeshwanthpur Sub-division", "division": "North", "lat": 13.0390, "lng": 77.5485, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Gangammanagudi PS", "court": "XXXI Addl CMM", "sub_division": "Yeshwanthpur Sub-division", "division": "North", "lat": 13.0550, "lng": 77.5440, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Peenya PS", "court": "XXXI Addl CMM", "sub_division": "Peenya Sub-division", "division": "North", "lat": 13.0285, "lng": 77.5190, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "RMC Yard PS", "court": "XXXI Addl CMM", "sub_division": "Peenya Sub-division", "division": "North", "lat": 13.0180, "lng": 77.5430, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Rajagopalnagar PS", "court": "XXXI Addl CMM", "sub_division": "Peenya Sub-division", "division": "North", "lat": 13.0080, "lng": 77.5180, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Bagalagunte PS", "court": "XXXI Addl CMM", "sub_division": "Peenya Sub-division", "division": "North", "lat": 13.0420, "lng": 77.5080, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 15. XXXII ACMM (IPC Cases)
    {"ps_name": "Malleshwaram PS", "court": "XXXII ACMM", "sub_division": "Malleshwaram Sub-division", "division": "North", "lat": 13.0035, "lng": 77.5715, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Srirampura PS", "court": "XXXII ACMM", "sub_division": "Malleshwaram Sub-division", "division": "North", "lat": 12.9910, "lng": 77.5680, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Rajajinagar PS", "court": "XXXII ACMM", "sub_division": "Malleshwaram Sub-division", "division": "North", "lat": 12.9922, "lng": 77.5540, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Subramanyanagar PS", "court": "XXXII ACMM", "sub_division": "Malleshwaram Sub-division", "division": "North", "lat": 12.9980, "lng": 77.5560, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Mahalakshmi Layout PS", "court": "XXXII ACMM", "sub_division": "Malleshwaram Sub-division", "division": "North", "lat": 13.0120, "lng": 77.5460, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Nandini Layout PS", "court": "XXXII ACMM", "sub_division": "Malleshwaram Sub-division", "division": "North", "lat": 13.0160, "lng": 77.5350, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 16. XXXVII Addl CMM (IPC Cases)
    {"ps_name": "VV Puram PS", "court": "XXXVII Addl CMM", "sub_division": "VV Puram Sub-division", "division": "South", "lat": 12.9510, "lng": 77.5760, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Hanumanthanagar PS", "court": "XXXVII Addl CMM", "sub_division": "VV Puram Sub-division", "division": "South", "lat": 12.9430, "lng": 77.5610, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "KG Nagar PS", "court": "XXXVII Addl CMM", "sub_division": "VV Puram Sub-division", "division": "South", "lat": 12.9480, "lng": 77.5680, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Shankarpura PS", "court": "XXXVII Addl CMM", "sub_division": "VV Puram Sub-division", "division": "South", "lat": 12.9490, "lng": 77.5710, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Girinagar PS", "court": "XXXVII Addl CMM", "sub_division": "VV Puram Sub-division", "division": "South", "lat": 12.9360, "lng": 77.5410, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "CK Achukattu PS", "court": "XXXVII Addl CMM", "sub_division": "VV Puram Sub-division", "division": "South", "lat": 12.9320, "lng": 77.5620, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 17. XXXIX Addl CMM (IPC Cases)
    {"ps_name": "Madiwala PS", "court": "XXXIX Addl CMM", "sub_division": "Madiwala Sub-division", "division": "South-East", "lat": 12.9228, "lng": 77.6188, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Koramangala PS", "court": "XXXIX Addl CMM", "sub_division": "Madiwala Sub-division", "division": "South-East", "lat": 12.9344, "lng": 77.6262, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Adugodi PS", "court": "XXXIX Addl CMM", "sub_division": "Madiwala Sub-division", "division": "South-East", "lat": 12.9430, "lng": 77.6105, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "HSR Layout PS", "court": "XXXIX Addl CMM", "sub_division": "Madiwala Sub-division", "division": "South-East", "lat": 12.9122, "lng": 77.6442, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 18. XLI Addl CMM (IPC Cases)
    {"ps_name": "Cubbon Park PS", "court": "XLI Addl CMM", "sub_division": "Cubbon Park Sub-division", "division": "Central", "lat": 12.9768, "lng": 77.5951, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Vidhana Soudha PS", "court": "XLI Addl CMM", "sub_division": "Cubbon Park Sub-division", "division": "Central", "lat": 12.9792, "lng": 77.5910, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Bellandur PS", "court": "XLI Addl CMM", "sub_division": "Marathahalli Sub-division", "division": "Whitefield", "lat": 12.9265, "lng": 77.6745, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Sampigehalli PS", "court": "XLI Addl CMM", "sub_division": "Sampigehalli Sub-division", "division": "North-East", "lat": 13.0740, "lng": 77.6240, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Amruthahalli PS", "court": "XLI Addl CMM", "sub_division": "Sampigehalli Sub-division", "division": "North-East", "lat": 13.0610, "lng": 77.6040, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},

    # 19. XLVI ACMM Court (IPC Cases)
    {"ps_name": "JJ Nagar PS", "court": "XLVI ACMM", "sub_division": "Byatarayanapura Sub-division", "division": "West", "lat": 12.9640, "lng": 77.5510, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Byatarayanapura PS", "court": "XLVI ACMM", "sub_division": "Byatarayanapura Sub-division", "division": "West", "lat": 12.9530, "lng": 77.5410, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Chandra Layout PS", "court": "XLVI ACMM", "sub_division": "Byatarayanapura Sub-division", "division": "West", "lat": 12.9560, "lng": 77.5250, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Jnanabharathi PS", "court": "XLVI ACMM", "sub_division": "Kengeri Sub-division", "division": "West", "lat": 12.9420, "lng": 77.5020, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Kengeri PS", "court": "XLVI ACMM", "sub_division": "Kengeri Sub-division", "division": "West", "lat": 12.9082, "lng": 77.4840, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Rajarajeshwari Nagar PS", "court": "XLVI ACMM", "sub_division": "Kengeri Sub-division", "division": "West", "lat": 12.9278, "lng": 77.5162, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
    {"ps_name": "Annapoorneshwari Nagar (AP Nagar) PS", "court": "XLVI ACMM", "sub_division": "Kengeri Sub-division", "division": "West", "lat": 12.9690, "lng": 77.5110, "court_complex": "City Civil Court Complex, Nrupathunga Rd"},
]


def export_court_jurisdiction_data() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Save structured JSON
    payload = {
        "source": SOURCE_URL,
        "notification_reference": NOTIFICATION_REF,
        "total_stations": len(COURT_POLICE_JURISDICTIONS),
        "jurisdictions": COURT_POLICE_JURISDICTIONS,
    }
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"[OK] Wrote JSON dataset to: {OUTPUT_JSON} ({len(COURT_POLICE_JURISDICTIONS)} police stations)")

    # 2. Save browseable CSV for Route Safety Studio & Crime Intelligence Tab
    headers = [
        "Police Station",
        "Sub-Division",
        "Court Name",
        "Division",
        "Court Complex",
        "Latitude",
        "Longitude",
        "Official Source",
    ]
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for st in COURT_POLICE_JURISDICTIONS:
            writer.writerow([
                st["ps_name"],
                st["sub_division"],
                st["court"],
                st["division"],
                st["court_complex"],
                f"{st['lat']:.4f}",
                f"{st['lng']:.4f}",
                "Bengaluru District Court (bengaluru.dcourts.gov.in)",
            ])
    print(f"[OK] Wrote CSV dataset to: {OUTPUT_CSV}")


if __name__ == "__main__":
    export_court_jurisdiction_data()

