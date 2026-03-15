import seaborn as sns
import json
import matplotlib.pyplot as plt

with open('functions_count_by_version.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# print(data)
xx = list(data.keys())
x = [key.split('-')[-1] for key in xx]
y = [data[key]['cnt'] for key in xx]

plt.figure(figsize=(24, 12))
# plt.xticks(rotation=45)
line_plot = sns.lineplot(x=x, y=y)

# 在每个数据点上标注数值
for i, (xi, yi) in enumerate(zip(x, y)):
    plt.annotate(str(yi), (xi, yi), 
                textcoords="offset points", 
                xytext=(0,10), 
                ha='center', 
                fontsize=10)

plt.xlabel('Version')
plt.ylabel('Buildin Function Count')
plt.title('PostgreSQL Buildin Function Count Across Versions')
plt.savefig('PostgreSQL buildin_function_count.png')
plt.show()