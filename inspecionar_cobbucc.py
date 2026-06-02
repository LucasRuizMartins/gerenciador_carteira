import pandas as pd

xl = pd.ExcelFile('cobbucc.xlsx')
print('Abas:', xl.sheet_names)

for sheet in xl.sheet_names:
    print(f'\n=== ABA: {sheet} ===')
    df = pd.read_excel('cobbucc.xlsx', sheet_name=sheet, header=None, nrows=30)
    print(df.to_string())
    print()
