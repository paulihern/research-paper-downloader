import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

# -------------------------
# 1) Input:major count
# -------------------------
nu_counts = {
    "Applied Math": 94,
    "Biomedical Engineering": 265,
    "Chemical Engineering": 146,
    "Civil Engineering": 88,
    "Computer Engineering": 142,
    "Computer Science": 409,
    "Electrical Engineering": 129,
    "Environmental Engineering": 46,
    "Industrial Engineering": 257,
    "Manufacturing and Design Engineering": 66,
    "Materials Science and Engineering": 98,
    "McCormick Integrated Engineering Studies": 1,
    "Undecided": 32,
}
uiuc_counts = {
    "Agricultural & Biological Engr": 43,
    "Engineering Physics": 9,
    "Physics": 538,
    "Computer Science & Physics": 73,
    "Civil Engineering": 747,
    "Environmental Engineering": 161,
    "Bioengineering": 441,
    "Neural Engineering": 68,
    "Computer Science & Bioengineering": 60,
    "Industrial Engineering": 349,
    "Systems Engineering & Design": 394,
    "Computer Science": 1070,
    "Engineering Undeclared": 460,
    "Aerospace Engineering": 845,
    "Engineering Mechanics": 148,
    "Mechanical Engineering": 1128,
    "Materials Science & Engr": 375,
    "Computer Engineering": 1232,
    "Electrical Engineering": 1043,
    "Nuclear, Plasma, Radiological Engr": 116,
}

# quick sanity checks
nu_total = sum(nu_counts.values())
uiuc_total = sum(uiuc_counts.values())
print("NU total:", nu_total)      # expect 1773
print("UIUC total:", uiuc_total)  # expect 9300

# weights tables
nu_w = pd.DataFrame({"major": list(nu_counts.keys()), "count": list(nu_counts.values())})
nu_w["prob"] = nu_w["count"] / nu_total

uiuc_w = pd.DataFrame({"major": list(uiuc_counts.keys()), "count": list(uiuc_counts.values())})
uiuc_w["prob"] = uiuc_w["count"] / uiuc_total

nu_w.to_csv("nu_major_weights.csv", index=False)
uiuc_w.to_csv("uiuc_major_weights.csv", index=False)

# -------------------------
# 2) set:scale
# -------------------------
n_nu = 2000
n_uiuc = 2000  #  balanced；according to the real proportion int(n_nu * (9300/1773))

# -------------------------
# 3) demographic generation rules
# -------------------------
gender_items = ["F", "M", "NB", "Unknown"]
gender_probs = [0.40, 0.55, 0.03, 0.02]

uiuc_year_counts = np.array([928, 2020, 2365, 4063], dtype=float)
uiuc_year_probs = uiuc_year_counts / uiuc_year_counts.sum()

# NU：Evenly divide the four grades
nu_year_probs = np.array([0.25, 0.25, 0.25, 0.25])

def sample_year(n, probs):
    return rng.choice([1,2,3,4], size=n, p=probs)

def gen_age(year_arr):
    # base: 17 + year, with a 30% chance +1
    age = 17 + year_arr + rng.binomial(1, 0.30, size=len(year_arr))
    # seniors: extra 15% chance +1 (late graduation)
    senior_mask = (year_arr == 4)
    age[senior_mask] += rng.binomial(1, 0.15, size=senior_mask.sum())
    return age

# -------------------------
# 4) seed keywords (simple dictionary)
# -------------------------
seed_bank = {
    "Mechanical Engineering": ["robotics", "dynamics", "thermodynamics", "manufacturing", "materials", "controls"],
    "Industrial Engineering": ["optimization", "supply chain", "simulation", "quality", "analytics", "operations"],
    "Computer Science": ["machine learning", "algorithms", "systems", "AI", "data", "NLP"],
    "Electrical Engineering": ["signals", "embedded", "circuits", "control", "communications", "power"],
    "Computer Engineering": ["embedded", "hardware", "systems", "architecture", "IoT", "computer vision"],
    "Civil Engineering": ["structures", "transportation", "water", "geotech", "sustainability", "risk"],
    "Materials Science & Engr": ["polymers", "metals", "nanomaterials", "characterization", "processing", "manufacturing"],
    "Bioengineering": ["biomechanics", "imaging", "devices", "biomaterials", "modeling", "data"],
    # fallback for majors not listed: generic engineering set
    "_default": ["design", "data analysis", "modeling", "experiments", "programming", "team projects"]
}

def gen_seed_keywords(major, k=4):
    bank = seed_bank.get(major, seed_bank["_default"])
    return rng.choice(bank, size=min(k, len(bank)), replace=False).tolist()

# -------------------------
# 5) generate base tables
# -------------------------
def gen_students(school, n, weights_df, year_probs, prefix):
    majors = rng.choice(weights_df["major"], size=n, p=weights_df["prob"])
    years = sample_year(n, year_probs)
    ages = gen_age(years)
    genders = rng.choice(gender_items, size=n, p=gender_probs)

    df = pd.DataFrame({
        "student_id": [f"{prefix}_{i:06d}" for i in range(1, n+1)],
        "school": school,
        "major": majors,
        "year": years,
        "age": ages,
        "gender": genders
    })
    df["seed_keywords"] = df["major"].apply(lambda m: gen_seed_keywords(m, k=4))
    return df

nu_students = gen_students("NU", n_nu, nu_w, nu_year_probs, "NU_ENG")
uiuc_students = gen_students("UIUC", n_uiuc, uiuc_w, uiuc_year_probs, "UIUC_ENG")

students_base = pd.concat([nu_students, uiuc_students], ignore_index=True)
students_base.to_csv("students_virtual_engineering_base.csv", index=False)

print("Wrote:", "nu_major_weights.csv, uiuc_major_weights.csv, students_virtual_engineering_base.csv")
print(students_base.head())
