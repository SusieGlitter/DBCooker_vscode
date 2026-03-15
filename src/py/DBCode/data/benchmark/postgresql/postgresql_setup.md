以下是 PostgreSQL 9.5 在 **Linux** 系统上从源码编译和安装的详细步骤：

常用命令：
```
sudo ss -tlnp | grep :5432

./psql -U wz -d postgres

./pg_ctl restart -D /data/wei/db/postgres/pgdata -o "-p 5432"
```

---

### **1. 准备编译环境**
安装必要的依赖工具和库：
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y build-essential libreadline-dev zlib1g-dev flex bison git
```

---

### **2. 下载 PostgreSQL 9.5 源码 (Github源码链接)**
```bash
wget https://github.com/postgres/postgres/archive/refs/heads/REL9_5_STABLE.zip
unzip REL9_5_STABLE.zip

cd REL9_5_STABLE
```

---

### **3. 配置编译选项**
```bash
./configure --prefix=/usr/local/pgsql-9.5  # 指定安装目录
```
常用选项：
- `--with-openssl`：启用 SSL 支持
- `--with-python`：启用 Python 扩展
- `--with-perl`：启用 Perl 扩展

检查依赖是否完整：
```bash
./configure --help | grep "with"  # 查看所有可选模块
```

---

### **4. 编译源码**
```bash
make clean
make uninstall
make -j$(nproc)  # 使用所有CPU核心加速编译
```
- `-j$(nproc)`：根据 CPU 核心数并行编译（如 `make -j4`）。

---

### **5. 安装到系统**
```bash
make install
```

---

### **6. 创建数据库目录**
```bash
sudo mkdir -p /usr/local/pgsql-9.5/data
```

---

### **7. 初始化数据库**
```bash
/usr/local/pgsql-9.5/bin/initdb --pgdata=/data/wei/database/pgdata --username=xxx --auth=trust
```

---

### **8. 启动 PostgreSQL 服务**
```bash
/usr/local/pgsql-9.5/bin/pg_ctl -D /usr/local/pgsql-9.5/data -l logfile start
```
验证是否运行：
```bash
/usr/local/pgsql-9.5/bin/psql -l
```

---

### **9. 运行 PostgreSQL 测试脚本**
```bash
make installcheck PGUSER=xxx
```
分析测试脚本，检查测试结果（TODO）
```
/src/test/regress/results
```

### **10. 设置系统服务（可选）**
创建 Systemd 服务文件 `/etc/systemd/system/postgresql-9.5.service`：
```ini
[Unit]
Description=PostgreSQL 9.5 Database Server
After=network.target

[Service]
Type=forking
User=postgres
ExecStart=/usr/local/pgsql-9.5/bin/pg_ctl -D /usr/local/pgsql-9.5/data -l /usr/local/pgsql-9.5/logfile start
ExecStop=/usr/local/pgsql-9.5/bin/pg_ctl -D /usr/local/pgsql-9.5/data stop

[Install]
WantedBy=multi-user.target
```
启用服务：
```bash
sudo systemctl daemon-reload
sudo systemctl start postgresql-9.5
sudo systemctl enable postgresql-9.5
```

---

### **常见问题解决**
#### **1. 编译时报错 `configure: error: readline library not found`**
- **解决**：安装 `libreadline-dev`（Debian）或 `readline-devel`（RHEL）。

#### **2. 启动时报错 `could not create lock file`**
- **原因**：数据目录权限问题。
- **解决**：
  ```bash
  sudo chown -R postgres:postgres /usr/local/pgsql-9.5/data
  ```

#### **3. 需要升级到最新 9.5.x 版本**
- 下载补丁版本（如 9.5.25）并重新编译：
  ```bash
  wget https://ftp.postgresql.org/pub/source/v9.5.25/postgresql-9.5.25.tar.gz
  ```

---

### **总结**
| 步骤 | 命令 |
|------|------|
| **安装依赖** | `sudo apt-get install build-essential libreadline-dev` |
| **下载源码** | `wget https://ftp.postgresql.org/pub/source/v9.5.0/postgresql-9.5.0.tar.gz` |
| **编译安装** | `./configure --prefix=/usr/local/pgsql-9.5 && make -j4 && sudo make install` |
| **初始化DB** | `sudo su - postgres; /usr/local/pgsql-9.5/bin/initdb -D /usr/local/pgsql-9.5/data` |
| **启动服务** | `/usr/local/pgsql-9.5/bin/pg_ctl -D /usr/local/pgsql-9.5/data -l logfile start` |

完成上述步骤后，PostgreSQL 9.5 将以源码编译的方式运行。如需更高安全性，建议升级到 [支持的 PostgreSQL 版本](https://www.postgresql.org/support/versioning/)。
