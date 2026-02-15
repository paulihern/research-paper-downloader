import pandas as pd

df = pd.read_csv("papers_with_keywords_k10.csv")

CLUSTER_TO_FACTORY = {
    0: "Materials & Solid Mechanics",
    3: "Thermal-Fluid & Transport Phenomena",
    5: "Advanced Manufacturing & Devices",

    1: "Robotics & Intelligent Systems",
    2: "Robotics & Intelligent Systems",
    9: "Robotics & Intelligent Systems",

    4: "Biomedical & Biomechanical Engineering",
    8: "Biomedical & Biomechanical Engineering",

    6: "Systems, Education & Interdisciplinary",
    7: "Systems, Education & Interdisciplinary",
}

df["refined_factory"] = df["cluster_id"].map(CLUSTER_TO_FACTORY)

df.to_csv("papers_refined_factory.csv", index=False)

print("Saved: papers_refined_factory.csv")
