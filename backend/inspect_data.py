import pandas as pd

df1 = pd.read_csv(r"C:\Users\Vyshini.BM\Desktop\majorproject\smartgrid-digital-twin\ml-training\data\raw\RS_Session_267_AU_944_B_ii_a.csv")
print(df1.head())
print(df1.columns.tolist())

df2 = pd.read_csv(r"C:\Users\Vyshini.BM\Desktop\majorproject\smartgrid-digital-twin\ml-training\data\raw\Indias_Electricity_Consumption_Dataset.csv")
print(df2.head())
print(df2.columns.tolist())
print(df2["Dates"].min(), df2["Dates"].max(), len(df2))
print(df1.shape)