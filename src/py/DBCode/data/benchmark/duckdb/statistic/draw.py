import re

import matplotlib.pyplot as plt

with open('duckdb.txt', 'r', encoding='utf-8') as f:
    lines = [line.strip() for line in f if line.strip()]

x_labels = []
y_values = []

for i in range(0, len(lines), 2):
    version_line = lines[i]
    func_count_line = lines[i+1]
    # 提取括号内内容
    match = re.search(r'\((.*?)\)', version_line)
    if match:
        x_labels.append(match.group(1))
    else:
        x_labels.append(version_line)
    try:
        y_values.append(int(func_count_line))
    except ValueError:
        y_values.append(0)

x_labels.reverse()
y_values.reverse()

# 绘制折线图
plt.figure(figsize=(20, 12))
plt.plot(x_labels, y_values, marker='o')
plt.xlabel('version')
plt.ylabel('function count')
plt.title('DuckDB Function Count Over Versions')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('duckdb.png')
plt.show()