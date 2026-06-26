"""
populate_sac_rates.py
---------------------
Loads SAC_MSTR from HSN_SAC.xlsx (682 SAC codes).
Maps rates from Notification 3/2017-CT(Rate) as amended by 11/2025-CT(Rate).

The 11/2025 amendment only changed S.No.1 (Heading 9954 construction services
with certain conditions) from 18% → 9% CGST. All other rates come from 3/2017.

Run:
    .\\venv\\Scripts\\python.exe populate_sac_rates.py
"""

import math
import pandas as pd

MASTER_FILE = "HSN_SAC.xlsx"
OUTPUT_FILE = "gst_hsn_sac_master_v1.xlsx"
EFFECTIVE_DATE   = "2025-09-22"
NOTIFICATION_REF = "11/2025-CT(Rate)"    # amendment ref; base is 3/2017-CT(Rate)

# ---------------------------------------------------------------------------
# SAC rate table from Notification 3/2017-CT(Rate) as amended up to 11/2025
# Format: (sac_prefix, cgst_rate, igst_rate, description_note, condition_text, condition_type)
# Prefix matching: a SAC code matches if it starts with the prefix.
# More-specific prefixes take priority (longer prefix wins).
# ---------------------------------------------------------------------------
SAC_RATE_TABLE = [
    # -------------------------------------------------------------------------
    # Heading 9954 — Construction Services (amended by 11/2025: S.No.1 → 9% CGST)
    # -------------------------------------------------------------------------
    ("995411", 9.0, 18.0, "Construction of single/multi dwelling residential buildings",
     "Works contract for residential purpose", "supply_type"),
    ("995412", 9.0, 18.0, "Construction of other residential buildings (old age homes, hostels)", None, "none"),
    ("995413", 9.0, 18.0, "Construction of industrial buildings", None, "none"),
    ("995414", 9.0, 18.0, "Construction of commercial buildings", None, "none"),
    ("995415", 9.0, 18.0, "Construction of other non-residential buildings", None, "none"),
    ("995416", 9.0, 18.0, "Construction of other buildings NEC", None, "none"),
    ("995417", 6.0, 12.0, "Construction for affordable residential real estate project (RREP)",
     "affordable residential real estate project", "supply_type"),
    ("995418", 9.0, 18.0, "Construction services of other buildings (e-commerce operator not liable for registration)",
     "electronic commerce operator not liable for registration", "registration"),
    ("995419", 9.0, 18.0, "Services involving repair, alterations, additions to residential buildings", None, "none"),
    ("995421", 9.0, 18.0, "General construction services of highways, streets", None, "none"),
    ("995422", 9.0, 18.0, "General construction services of railways and metro", None, "none"),
    ("995423", 9.0, 18.0, "General construction services of bridges, elevated roads, tunnels", None, "none"),
    ("995424", 9.0, 18.0, "General construction services of local water/sewage pipelines", None, "none"),
    ("995425", 9.0, 18.0, "General construction services of long-distance underground pipelines", None, "none"),
    ("995426", 9.0, 18.0, "General construction services of power plants", None, "none"),
    ("995427", 9.0, 18.0, "General construction services of other industrial plants", None, "none"),
    ("995428", 9.0, 18.0, "General construction services of outdoor sports/recreation facilities", None, "none"),
    ("995429", 9.0, 18.0, "Services involving repair, alterations of infrastructure", None, "none"),
    ("995431", 9.0, 18.0, "Installation services of lifts, escalators, AC systems", None, "none"),
    ("995432", 9.0, 18.0, "Installation services of other building completion services", None, "none"),
    ("995433", 9.0, 18.0, "Installation services of other building equipment", None, "none"),
    ("995434", 9.0, 18.0, "Installation services of industrial machinery and equipment", None, "none"),
    ("995435", 9.0, 18.0, "Installation services of other plants and machinery", None, "none"),
    ("995436", 9.0, 18.0, "Services involving repair and maintenance of elevators", None, "none"),
    ("995439", 9.0, 18.0, "Other installation services NEC", None, "none"),
    ("995441", 9.0, 18.0, "Site preparation services including excavation", None, "none"),
    ("995442", 9.0, 18.0, "Building completion and finishing services", None, "none"),
    ("995443", 9.0, 18.0, "Other building completion services NEC", None, "none"),
    ("995444", 9.0, 18.0, "Painting services", None, "none"),
    ("995445", 9.0, 18.0, "Floor laying, wall tiling services", None, "none"),
    ("995446", 9.0, 18.0, "Joinery and carpentry services", None, "none"),
    ("995447", 9.0, 18.0, "Plastering services", None, "none"),
    ("995448", 9.0, 18.0, "Other specialised construction services NEC", None, "none"),
    ("995451", 9.0, 18.0, "Demolition services", None, "none"),
    ("995452", 9.0, 18.0, "Site preparation services NEC", None, "none"),
    ("995453", 9.0, 18.0, "Site preparation for mining", None, "none"),
    ("995454", 9.0, 18.0, "Water well drilling and related services", None, "none"),
    ("995455", 9.0, 18.0, "Test drilling and boring services", None, "none"),
    ("995456", 9.0, 18.0, "Steel reinforcing bar fabrication services", None, "none"),
    ("995459", 9.0, 18.0, "Other special trade construction services NEC", None, "none"),
    ("995461", 9.0, 18.0, "Sub-contracted services for construction of buildings", None, "none"),
    ("995462", 9.0, 18.0, "Sub-contracted services for infrastructure", None, "none"),
    ("995463", 9.0, 18.0, "Sub-contracted services for other installations", None, "none"),
    ("995468", 9.0, 18.0, "Other miscellaneous sub-contracted construction services NEC", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9963 — Accommodation, food and beverage services
    # -------------------------------------------------------------------------
    ("996311", 6.0, 12.0, "Room in a hotel/inn/club/guest house (declared tariff < Rs 7500)",
     "declared tariff less than Rs. 7500 per unit per day", "price_threshold"),
    ("996312", 9.0, 18.0, "Room in a hotel/inn/club/guest house (declared tariff >= Rs 7500)",
     "declared tariff of Rs. 7500 and above per unit per day", "price_threshold"),
    ("996321", 2.5, 5.0, "Food and beverage services in restaurants without ITC",
     "restaurants not claiming ITC", "none"),
    ("996322", 2.5, 5.0, "Food and beverage services in outdoor catering without ITC", None, "none"),
    ("996331", 9.0, 18.0, "Services by way of admission to amusement parks", None, "none"),
    ("9963",   9.0, 18.0, "Accommodation, food and beverage services (other)", None, "none"),  # catch-all

    # -------------------------------------------------------------------------
    # Heading 9964 — Passenger transport services
    # -------------------------------------------------------------------------
    ("996401", 0.0, 0.0, "Local transport of passengers by railways or metro", None, "none"),
    ("996402", 2.5, 5.0, "Rail transport of passengers (non-air-conditioned sleeper)",
     "non air-conditioned", "none"),
    ("996403", 6.0, 12.0, "Rail transport of passengers (first class/AC)", None, "none"),
    ("996404", 0.0, 0.0, "Bus transport of passengers (stage carriage)", None, "none"),
    ("996405", 6.0, 12.0, "Taxi/cab services for passenger transport", None, "none"),
    ("996406", 0.0, 0.0, "Rental services of motor vehicles (without operator) for personal use", None, "none"),
    ("996407", 0.0, 0.0, "Transport of passengers by air (economy class)",
     "economy class", "none"),
    ("996408", 6.0, 12.0, "Transport of passengers by air (other than economy)", None, "none"),
    ("996411", 0.0, 0.0, "Inland water transport for passengers", None, "none"),
    ("996421", 6.0, 12.0, "Sightseeing/tour operator services", None, "none"),
    ("9964",   6.0, 12.0, "Passenger transport services (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9965 — Goods transport services
    # -------------------------------------------------------------------------
    ("996511", 0.0, 0.0, "Road transport of goods by GTA (if GTA opts for paying GST)", None, "none"),
    ("996512", 0.0, 0.0, "Road transport of goods in a goods carriage", None, "none"),
    ("996513", 0.0, 0.0, "Rail freight transport services", None, "none"),
    ("996521", 0.0, 0.0, "Coastal/inland water transport of goods", None, "none"),
    ("996531", 6.0, 12.0, "Air freight transport services", None, "none"),
    ("996532", 6.0, 12.0, "Space transport services for freight", None, "none"),
    ("996601", 6.0, 12.0, "Rental of road vehicles with operators", None, "none"),
    ("996602", 6.0, 12.0, "Rental of water vessels with operators", None, "none"),
    ("996603", 6.0, 12.0, "Rental of aircraft with operators", None, "none"),
    ("9965",   2.5, 5.0,  "Goods transport services (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9966 — Rental/leasing services of transport equipment
    # -------------------------------------------------------------------------
    ("996601", 6.0, 12.0, "Rental of road vehicles with operators", None, "none"),
    ("996611", 9.0, 18.0, "Rental services of road vehicles without operators", None, "none"),
    ("996612", 9.0, 18.0, "Rental services of water vessels without operators", None, "none"),
    ("996613", 9.0, 18.0, "Rental services of aircraft without operators", None, "none"),
    ("9966",   9.0, 18.0, "Rental/leasing of transport equipment (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9967 — Supporting services in transport
    # -------------------------------------------------------------------------
    ("996711", 9.0, 18.0, "Cargo handling services (including container services)", None, "none"),
    ("996712", 9.0, 18.0, "Storage and warehousing services", None, "none"),
    ("996713", 9.0, 18.0, "Customs house agent services", None, "none"),
    ("996719", 9.0, 18.0, "Other supporting services for transport NEC", None, "none"),
    ("9967",   9.0, 18.0, "Supporting services in transport (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9968 — Postal and courier services
    # -------------------------------------------------------------------------
    ("996811", 0.0, 0.0, "Postal services by India Post", None, "none"),
    ("996812", 9.0, 18.0, "Courier services", None, "none"),
    ("9968",   9.0, 18.0, "Postal and courier services (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9969 — Electricity, gas and water distribution services
    # -------------------------------------------------------------------------
    ("996911", 0.0, 0.0, "Transmission and distribution of electricity", None, "none"),
    ("996912", 0.0, 0.0, "Distribution of natural gas through pipeline", None, "none"),
    ("996913", 0.0, 0.0, "Water supply services", None, "none"),
    ("9969",   0.0, 0.0, "Electricity, gas and water distribution (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9971 — Financial and related services
    # -------------------------------------------------------------------------
    ("997111", 9.0, 18.0, "Financial leasing services", None, "none"),
    ("997112", 9.0, 18.0, "Hire purchase financial services", None, "none"),
    ("997113", 9.0, 18.0, "Credit card services", None, "none"),
    ("997119", 9.0, 18.0, "Other financial services NEC", None, "none"),
    ("997120", 9.0, 18.0, "Insurance/pension fund management services", None, "none"),
    ("997131", 9.0, 18.0, "Life insurance services", None, "none"),
    ("997132", 9.0, 18.0, "Accident and health insurance services", None, "none"),
    ("997133", 9.0, 18.0, "Property insurance services", None, "none"),
    ("997139", 9.0, 18.0, "Other insurance services NEC", None, "none"),
    ("997141", 9.0, 18.0, "Pension fund management services", None, "none"),
    ("997142", 9.0, 18.0, "Other long-term benefit plan management services", None, "none"),
    ("997150", 9.0, 18.0, "Security and commodity brokerage services", None, "none"),
    ("997171", 9.0, 18.0, "Foreign exchange services", None, "none"),
    ("997172", 9.0, 18.0, "Money transfer services", None, "none"),
    ("997173", 9.0, 18.0, "ATM management services", None, "none"),
    ("9971",   9.0, 18.0, "Financial and related services (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9972 — Real estate services
    # -------------------------------------------------------------------------
    ("997211", 9.0, 18.0, "Renting/leasing of residential property", None, "none"),
    ("997212", 9.0, 18.0, "Renting/leasing of commercial property", None, "none"),
    ("997213", 9.0, 18.0, "Trade services of buildings and land", None, "none"),
    ("997221", 9.0, 18.0, "Property management services", None, "none"),
    ("997222", 9.0, 18.0, "Real estate appraisal services", None, "none"),
    ("9972",   9.0, 18.0, "Real estate services (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9973 — Leasing/rental without operators
    # -------------------------------------------------------------------------
    ("997311", 9.0, 18.0, "Financial leasing (machinery & equipment)", None, "none"),
    ("997312", 9.0, 18.0, "Operating leasing services of machinery & equipment", None, "none"),
    ("997313", 9.0, 18.0, "Leasing of computers and peripherals", None, "none"),
    ("997314", 9.0, 18.0, "Leasing of telecom equipment", None, "none"),
    ("997315", 9.0, 18.0, "Leasing of other office machinery", None, "none"),
    ("997319", 9.0, 18.0, "Leasing of other machinery NEC", None, "none"),
    ("997321", 9.0, 18.0, "Leasing of land and buildings", None, "none"),
    ("997331", 9.0, 18.0, "Leasing of household goods", None, "none"),
    ("997339", 9.0, 18.0, "Leasing of other personal effects", None, "none"),
    ("9973",   9.0, 18.0, "Leasing/rental services without operators (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9981 — Research and development services
    # -------------------------------------------------------------------------
    ("9981",   6.0, 12.0, "Research and development services", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9982 — Legal and accounting services
    # -------------------------------------------------------------------------
    ("998211", 9.0, 18.0, "Legal advisory and representation services", None, "none"),
    ("998212", 9.0, 18.0, "Legal documentation and certification services", None, "none"),
    ("998221", 9.0, 18.0, "Accounting and bookkeeping services", None, "none"),
    ("998222", 9.0, 18.0, "Financial auditing services", None, "none"),
    ("998223", 9.0, 18.0, "Tax consultancy and preparation services", None, "none"),
    ("998224", 9.0, 18.0, "Insolvency and receivership services", None, "none"),
    ("9982",   9.0, 18.0, "Legal and accounting services (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9983 — Professional and management consulting
    # -------------------------------------------------------------------------
    ("998311", 9.0, 18.0, "Management consulting and advisory services", None, "none"),
    ("998312", 9.0, 18.0, "Business and production management advisory services", None, "none"),
    ("998313", 9.0, 18.0, "IT related management consulting services", None, "none"),
    ("998314", 9.0, 18.0, "Engineering/architectural advisory services", None, "none"),
    ("998315", 9.0, 18.0, "Environmental advisory services", None, "none"),
    ("998319", 9.0, 18.0, "Other management consulting services NEC", None, "none"),
    ("998321", 9.0, 18.0, "Advertising and related services", None, "none"),
    ("998322", 9.0, 18.0, "Market research and public opinion polling services", None, "none"),
    ("998331", 9.0, 18.0, "Human resource recruitment and supply services", None, "none"),
    ("998332", 9.0, 18.0, "Agency staff supply services", None, "none"),
    ("998333", 9.0, 18.0, "Contract staffing services", None, "none"),
    ("9983",   9.0, 18.0, "Professional/management consulting services (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9984 — Telecommunication, broadcasting and IT services
    # -------------------------------------------------------------------------
    ("998411", 9.0, 18.0, "Telephone and other telecommunication services", None, "none"),
    ("998412", 9.0, 18.0, "Internet access services", None, "none"),
    ("998413", 9.0, 18.0, "Private network services", None, "none"),
    ("998414", 9.0, 18.0, "Telex services", None, "none"),
    ("998419", 9.0, 18.0, "Other telecommunications services NEC", None, "none"),
    ("998421", 9.0, 18.0, "Radio and TV broadcast and related services", None, "none"),
    ("998431", 9.0, 18.0, "Motion picture production and distribution services", None, "none"),
    ("998432", 9.0, 18.0, "Video tape production, copying and related services", None, "none"),
    ("998433", 9.0, 18.0, "Sound recording and related services", None, "none"),
    ("998434", 9.0, 18.0, "Theatrical production and related services", None, "none"),
    ("998441", 9.0, 18.0, "IT design and development services", None, "none"),
    ("998442", 9.0, 18.0, "IT infrastructure and network management services", None, "none"),
    ("998443", 9.0, 18.0, "Maintenance, repair and installation services of computers", None, "none"),
    ("998444", 9.0, 18.0, "Data processing services", None, "none"),
    ("998445", 9.0, 18.0, "Data base services", None, "none"),
    ("998446", 9.0, 18.0, "Other IT related services NEC", None, "none"),
    ("9984",   9.0, 18.0, "Telecom, broadcasting and IT services (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9985 — Support services
    # -------------------------------------------------------------------------
    ("998511", 9.0, 18.0, "Credit investigation and reporting services", None, "none"),
    ("998512", 9.0, 18.0, "Debt collection services", None, "none"),
    ("998513", 9.0, 18.0, "Leasing of intellectual property, franchise", None, "none"),
    ("998514", 9.0, 18.0, "Event management services", None, "none"),
    ("998515", 9.0, 18.0, "Packaging services", None, "none"),
    ("998516", 9.0, 18.0, "Document preparation services", None, "none"),
    ("998521", 9.0, 18.0, "Building cleaning services", None, "none"),
    ("998522", 9.0, 18.0, "Disinfecting and exterminating services", None, "none"),
    ("998523", 9.0, 18.0, "Furnishing services", None, "none"),
    ("998524", 9.0, 18.0, "Chimney cleaning services", None, "none"),
    ("998531", 9.0, 18.0, "Postal courier services (private)", None, "none"),
    ("998532", 9.0, 18.0, "Messenger services", None, "none"),
    ("998541", 9.0, 18.0, "Credit card and money transfer services", None, "none"),
    ("998542", 9.0, 18.0, "Convention and trade show organizer services", None, "none"),
    ("998543", 9.0, 18.0, "Security guard services", None, "none"),
    ("998544", 9.0, 18.0, "Armored car services", None, "none"),
    ("998545", 9.0, 18.0, "Guard dog services", None, "none"),
    ("998546", 9.0, 18.0, "Surveillance and detective services", None, "none"),
    ("998547", 9.0, 18.0, "Alarm systems installation and monitoring", None, "none"),
    ("998551", 9.0, 18.0, "Telephone answering services", None, "none"),
    ("998552", 9.0, 18.0, "Photocopying services", None, "none"),
    ("998553", 9.0, 18.0, "Translation and interpretation services", None, "none"),
    ("998559", 9.0, 18.0, "Other business support services NEC", None, "none"),
    ("9985",   9.0, 18.0, "Support services (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9986 — Agriculture, fishing, forestry support services
    # -------------------------------------------------------------------------
    ("998611", 2.5, 5.0, "Support services for crop production", None, "none"),
    ("998612", 2.5, 5.0, "Support services for animal husbandry", None, "none"),
    ("998613", 2.5, 5.0, "Support services for fishing", None, "none"),
    ("998614", 2.5, 5.0, "Support services for forestry and logging", None, "none"),
    ("998619", 2.5, 5.0, "Other support services for agriculture NEC", None, "none"),
    ("9986",   2.5, 5.0, "Agriculture, fishing, forestry support services (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9987 — Maintenance, repair and installation services (non-construction)
    # -------------------------------------------------------------------------
    ("998711", 9.0, 18.0, "Maintenance/repair of motor vehicles and motorcycles", None, "none"),
    ("998712", 9.0, 18.0, "Maintenance/repair of railway rolling stock", None, "none"),
    ("998713", 9.0, 18.0, "Maintenance/repair of aircraft and spacecraft", None, "none"),
    ("998714", 9.0, 18.0, "Maintenance/repair of vessels and floating structures", None, "none"),
    ("998715", 9.0, 18.0, "Maintenance/repair of professional/scientific equipment", None, "none"),
    ("998716", 9.0, 18.0, "Maintenance/repair of computers and peripherals", None, "none"),
    ("998717", 9.0, 18.0, "Maintenance/repair of other office machinery", None, "none"),
    ("998718", 9.0, 18.0, "Maintenance/repair of household appliances and equipment", None, "none"),
    ("998719", 9.0, 18.0, "Maintenance/repair of other industrial machinery", None, "none"),
    ("998721", 9.0, 18.0, "Installation services of general-purpose machinery", None, "none"),
    ("998722", 9.0, 18.0, "Installation services of special-purpose machinery", None, "none"),
    ("9987",   9.0, 18.0, "Maintenance, repair and installation services (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9988 — Manufacturing services on physical inputs
    # -------------------------------------------------------------------------
    ("998811", 2.5, 5.0, "Textile yarn and related products job work", None, "none"),
    ("998812", 2.5, 5.0, "Knitted/crocheted fabrics job work", None, "none"),
    ("998813", 2.5, 5.0, "Wearing apparel job work", None, "none"),
    ("998814", 2.5, 5.0, "Leather/related products job work", None, "none"),
    ("998815", 2.5, 5.0, "Wood and wood products job work", None, "none"),
    ("998816", 2.5, 5.0, "Paper and paper products job work", None, "none"),
    ("998817", 2.5, 5.0, "Publishing/printing services job work", None, "none"),
    ("998818", 2.5, 5.0, "Chemical and pharmaceutical products job work", None, "none"),
    ("998819", 2.5, 5.0, "Rubber/plastic products job work", None, "none"),
    ("998821", 2.5, 5.0, "Non-metallic mineral products job work", None, "none"),
    ("998822", 6.0, 12.0, "Fabricated metal products job work", None, "none"),
    ("998823", 6.0, 12.0, "General-purpose machinery job work", None, "none"),
    ("998824", 6.0, 12.0, "Special-purpose machinery job work", None, "none"),
    ("998825", 6.0, 12.0, "IT and computer hardware job work", None, "none"),
    ("998826", 6.0, 12.0, "Electronic components job work", None, "none"),
    ("998827", 6.0, 12.0, "Electrical equipment job work", None, "none"),
    ("998828", 6.0, 12.0, "Vehicle manufacturing job work", None, "none"),
    ("998829", 6.0, 12.0, "Other transport equipment job work", None, "none"),
    ("998831", 6.0, 12.0, "Furniture manufacturing job work", None, "none"),
    ("998832", 6.0, 12.0, "Jewellery manufacturing job work", None, "none"),
    ("998833", 6.0, 12.0, "Musical instruments manufacturing job work", None, "none"),
    ("998834", 6.0, 12.0, "Sports goods manufacturing job work", None, "none"),
    ("998839", 6.0, 12.0, "Other manufacturing services NEC", None, "none"),
    ("9988",   6.0, 12.0, "Manufacturing services on physical inputs (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9989 — Other manufacturing services
    # -------------------------------------------------------------------------
    ("998911", 6.0, 12.0, "Newspaper printing services", None, "none"),
    ("998912", 6.0, 12.0, "Book publishing services", None, "none"),
    ("998913", 6.0, 12.0, "Music recording and related services", None, "none"),
    ("9989",   6.0, 12.0, "Other manufacturing services (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9991 — Public administration and other government services
    # -------------------------------------------------------------------------
    ("9991",   0.0, 0.0, "Public administration and government services", None, "entity_type"),

    # -------------------------------------------------------------------------
    # Heading 9992 — Education services
    # -------------------------------------------------------------------------
    ("999210", 0.0, 0.0, "Pre-primary education services", None, "none"),
    ("999211", 0.0, 0.0, "Primary education services", None, "none"),
    ("999212", 0.0, 0.0, "Secondary education services (tech/vocational)", None, "none"),
    ("999213", 0.0, 0.0, "Secondary education services (general)", None, "none"),
    ("999214", 0.0, 0.0, "Higher secondary education services (tech/vocational)", None, "none"),
    ("999215", 0.0, 0.0, "Higher secondary education services (general)", None, "none"),
    ("999216", 0.0, 0.0, "Higher education services (tech/vocational) degree granting", None, "none"),
    ("999217", 0.0, 0.0, "Higher education services (general/professional) degree granting", None, "none"),
    ("999219", 0.0, 0.0, "Other education and training NEC", None, "none"),
    ("999221", 9.0, 18.0, "Cultural education services", None, "none"),
    ("999222", 9.0, 18.0, "Fitness/physical education services", None, "none"),
    ("999223", 9.0, 18.0, "Commercial training services", None, "none"),
    ("999224", 9.0, 18.0, "Vocational education and training services NEC", None, "none"),
    ("999229", 9.0, 18.0, "Other education services NEC", None, "none"),
    ("9992",   0.0, 0.0, "Education services (other, exempt)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9993 — Human health and social care services
    # -------------------------------------------------------------------------
    ("999311", 0.0, 0.0, "In-patient services by hospitals/clinical establishments", None, "none"),
    ("999312", 0.0, 0.0, "Medical and dental services by clinical establishments", None, "none"),
    ("999313", 0.0, 0.0, "Childbirth and related services", None, "none"),
    ("999314", 0.0, 0.0, "Nursing and physiotherapist services", None, "none"),
    ("999315", 0.0, 0.0, "Ambulance transport services", None, "none"),
    ("999316", 0.0, 0.0, "Blood bank services", None, "none"),
    ("999317", 0.0, 0.0, "Other health services NEC", None, "none"),
    ("999321", 0.0, 0.0, "Residential care services for elderly/disabled", None, "none"),
    ("999322", 0.0, 0.0, "Child day-care services", None, "none"),
    ("999323", 0.0, 0.0, "Other social care services NEC", None, "none"),
    ("9993",   0.0, 0.0, "Human health and social care services (exempt)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9994 — Sewage and waste collection/treatment services
    # -------------------------------------------------------------------------
    ("999411", 0.0, 0.0, "Sewage services", None, "none"),
    ("999412", 0.0, 0.0, "Septic tank emptying and cleaning services", None, "none"),
    ("999421", 0.0, 0.0, "Solid waste collection services", None, "none"),
    ("999422", 0.0, 0.0, "Solid waste treatment services", None, "none"),
    ("999431", 9.0, 18.0, "Remediation and clean-up services", None, "none"),
    ("999432", 9.0, 18.0, "Other sanitation services NEC", None, "none"),
    ("9994",   0.0, 0.0, "Sewage and waste services (other, exempt)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9995 — Services of membership organisations
    # -------------------------------------------------------------------------
    ("999510", 9.0, 18.0, "Services of commercial, employer and professional organisations", None, "none"),
    ("999520", 9.0, 18.0, "Services of trade unions", None, "none"),
    ("999540", 9.0, 18.0, "Services of religious organisations",
     "religious organisation", "entity_type"),
    ("999560", 0.0, 0.0, "Services of political organisations", None, "entity_type"),
    ("999570", 0.0, 0.0, "Services of other membership organisations", None, "none"),
    ("9995",   9.0, 18.0, "Services of membership organisations (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9996 — Recreational, cultural and sporting services
    # -------------------------------------------------------------------------
    ("999611", 9.0, 18.0, "Admission to cultural events, museums, libraries", None, "none"),
    ("999612", 9.0, 18.0, "Gambling and lottery services",
     "gambling, lottery, horse racing", "supply_type"),
    ("999613", 9.0, 18.0, "Services related to motion picture, TV, radio production", None, "none"),
    ("999614", 9.0, 18.0, "Original artistic and literary creation services", None, "none"),
    ("999615", 9.0, 18.0, "Services of performing artists", None, "none"),
    ("999619", 9.0, 18.0, "Other cultural services NEC", None, "none"),
    ("999621", 9.0, 18.0, "Admission to sporting events", None, "none"),
    ("999622", 9.0, 18.0, "Sporting activity services", None, "none"),
    ("999629", 9.0, 18.0, "Other amusement and recreation services", None, "none"),
    ("9996",   9.0, 18.0, "Recreational, cultural and sporting services (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9997 — Other services
    # -------------------------------------------------------------------------
    ("999711", 9.0, 18.0, "Laundry and dry-cleaning services", None, "none"),
    ("999712", 9.0, 18.0, "Hairdressing and beauty treatment services", None, "none"),
    ("999713", 9.0, 18.0, "Funeral, cremation and undertaking services", None, "none"),
    ("999714", 9.0, 18.0, "Veterinary services", None, "none"),
    ("999715", 9.0, 18.0, "Shoe-shining, car-washing and other personal services", None, "none"),
    ("999719", 9.0, 18.0, "Other personal services NEC", None, "none"),
    ("999721", 9.0, 18.0, "Services provided by extraterritorial organisations", None, "none"),
    ("9997",   9.0, 18.0, "Other services (other)", None, "none"),

    # -------------------------------------------------------------------------
    # Heading 9998 — Domestic services
    # -------------------------------------------------------------------------
    ("9998",   0.0, 0.0, "Domestic household services (exempt)", None, "none"),

    # -------------------------------------------------------------------------
    # Top-level chapter 99 catch-all (only if nothing else matches)
    # -------------------------------------------------------------------------
    ("99",     9.0, 18.0, "Services - general (other)", None, "none"),
]

# Build a lookup: prefix → (cgst, igst, condition_text, condition_type)
# Sort by length desc so longest (most specific) prefix is tried first
SAC_LOOKUP = sorted(
    [(p, cgst, igst, desc, cond, ctype) for p, cgst, igst, desc, cond, ctype in SAC_RATE_TABLE],
    key=lambda x: -len(x[0])
)

CONDITION_KEYWORDS = [
    "branded", "unbranded", "pre-packaged", "labelled",
    "other than", "excluding", "where", "registered",
    "unregistered", "if ", "for use in", "used for",
    "for the purpose of", "government", "authority",
    "municipality", "works contract", "exceeding",
    "not exceeding", "above", "below", "export",
    "affordable", "religious", "lottery", "gambling",
]

def detect_condition_type(text: str) -> str:
    if not text:
        return "none"
    t = text.lower()
    if any(k in t for k in ["branded", "unbranded", "pre-packaged", "labelled"]):
        return "branding"
    if any(k in t for k in ["registered", "unregistered", "composition", "registration"]):
        return "registration"
    if any(k in t for k in ["works contract", "installation", "export", "affordable", "lottery", "gambling"]):
        return "supply_type"
    if any(k in t for k in ["exceeding", "not exceeding", "above", "below", "rs.", "7500", "price"]):
        return "price_threshold"
    if any(k in t for k in ["for use in", "used for", "for the purpose of"]):
        return "end_use"
    if any(k in t for k in ["government", "authority", "municipality", "religious", "political"]):
        return "entity_type"
    return "none"

def has_condition_kw(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return any(k in t for k in CONDITION_KEYWORDS)

def match_sac(code: str):
    """Return matching (cgst, igst, condition_text, condition_type) for a SAC code."""
    code_str = str(code).strip()
    for prefix, cgst, igst, _, cond, ctype in SAC_LOOKUP:
        if code_str.startswith(prefix):
            return cgst, igst, cond, ctype
    return None, None, None, "none"


def main():
    print("Loading SAC_MSTR from HSN_SAC.xlsx ...")
    sac_master = pd.read_excel(MASTER_FILE, sheet_name="SAC_MSTR")
    print(f"  {len(sac_master)} SAC codes loaded. Columns: {list(sac_master.columns)}")

    records = []
    matched = 0
    unmatched_codes = []

    for _, row in sac_master.iterrows():
        sac_raw = str(row["SAC_CD"]).strip()
        sac_desc = str(row["SAC_Description"]).strip()

        # Pad to 6 digits for 6-digit codes; keep 2/4-digit as-is
        digits = "".join(c for c in sac_raw if c.isdigit())
        if len(digits) >= 6:
            sac_code = digits[:6].ljust(6, "0")
        elif len(digits) == 4:
            sac_code = digits
        elif len(digits) == 2:
            sac_code = digits
        else:
            sac_code = digits

        cgst_rate, igst_rate, cond_text, cond_type = match_sac(sac_code)

        if cgst_rate is not None:
            matched += 1
        else:
            unmatched_codes.append(sac_code)

        # Determine has_condition from condition_text
        has_cond = has_condition_kw(cond_text) if cond_text else False
        effective_cond_type = detect_condition_type(cond_text) if cond_text else "none"

        records.append({
            "sac_code":         sac_code,
            "sac_description":  sac_desc,
            "cgst_rate":        cgst_rate,
            "igst_rate":        igst_rate,
            "cess_rate":        0,
            "condition_text":   cond_text,
            "condition_type":   effective_cond_type,
            "has_condition":    has_cond,
            "notification_ref": NOTIFICATION_REF,
            "effective_date":   EFFECTIVE_DATE,
            "needs_review":     cgst_rate is None,
        })

    sac_df = pd.DataFrame(records)
    print(f"\n  Matched: {matched} / {len(sac_df)}")
    print(f"  Unmatched (needs_review=True): {len(unmatched_codes)}")
    if unmatched_codes:
        print(f"  Unmatched codes: {unmatched_codes[:20]}")

    print("\nIGST rate distribution:")
    print(sac_df["igst_rate"].value_counts(dropna=False).to_string())

    # Load existing Excel sheets
    print("\nLoading existing Excel workbook ...")
    with pd.ExcelFile(OUTPUT_FILE) as xf:
        hsn_df      = pd.read_excel(xf, sheet_name="HSN_RATES")
        cond_df     = pd.read_excel(xf, sheet_name="CONDITIONS_REFERENCE")
        stats_df    = pd.read_excel(xf, sheet_name="SUMMARY_STATS")
        try:
            unmatched_df = pd.read_excel(xf, sheet_name="UNMATCHED_NOTIFICATIONS")
        except Exception:
            unmatched_df = pd.DataFrame()

    # Rebuild SUMMARY_STATS
    total_hsn   = len(hsn_df)
    total_sac   = len(sac_df)
    hsn_matched = int(hsn_df["cgst_rate"].notna().sum())
    sac_matched = int(sac_df["cgst_rate"].notna().sum())
    hsn_cond    = int(hsn_df["has_condition"].fillna(False).astype(bool).sum())
    sac_cond    = int(sac_df["has_condition"].fillna(False).astype(bool).sum())

    cess_numeric = pd.to_numeric(hsn_df.get("cess_rate", pd.Series()), errors="coerce").fillna(0)
    cess_count  = int((cess_numeric > 0).sum())

    hsn_sched   = hsn_df.groupby("schedule", dropna=False).size().reset_index(name="count")

    igst_dist = sac_df["igst_rate"].value_counts(dropna=False).reset_index()
    igst_dist.columns = ["igst_rate", "count"]

    summary_rows = [
        ("Total HSN codes",          total_hsn),
        ("Total SAC codes",          total_sac),
        ("HSN - Matched with rate",  hsn_matched),
        ("HSN - Unmatched",          total_hsn - hsn_matched),
        ("SAC - Matched with rate",  sac_matched),
        ("SAC - Unmatched",          total_sac - sac_matched),
        ("HSN Has conditions",       hsn_cond),
        ("SAC Has conditions",       sac_cond),
        ("Cess applicable count",    cess_count),
    ]
    for _, r in hsn_sched.iterrows():
        summary_rows.append((f"HSN Schedule: {r['schedule']}", int(r["count"])))
    for _, r in igst_dist.iterrows():
        summary_rows.append((f"SAC IGST Rate: {r['igst_rate']}%", int(r["count"])))

    new_stats_df = pd.DataFrame(summary_rows, columns=["Statistic", "Value"])

    # Write back
    print(f"\nWriting output to {OUTPUT_FILE} ...")
    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        hsn_df.to_excel(writer,      sheet_name="HSN_RATES",               index=False)
        sac_df.to_excel(writer,      sheet_name="SAC_RATES",               index=False)
        cond_df.to_excel(writer,     sheet_name="CONDITIONS_REFERENCE",    index=False)
        new_stats_df.to_excel(writer, sheet_name="SUMMARY_STATS",          index=False)
        unmatched_df.to_excel(writer, sheet_name="UNMATCHED_NOTIFICATIONS", index=False)

    print("\n=== DONE ===")
    print(f"  SAC_RATES rows  : {len(sac_df)}")
    print(f"  Matched         : {sac_matched}")
    print(f"  Needs review    : {total_sac - sac_matched}")
    print(f"  Output          : {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
