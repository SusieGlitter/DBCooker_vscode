## 1. 安装依赖
```bash
sudo apt-get update
sudo apt-get install -y git g++ cmake ninja-build libssl-dev
```

## 2. 下载duckdb源码
```bash
git clone https://github.com/duckdb/duckdb.git
cd duckdb
```

## 3. 编译安装
```bash
make
make release # same as plain make
make debug
GEN=ninja make # for use with Ninja
BUILD_BENCHMARK=1 make # Build with benchmarks
```

### 3.1 构建选项
| release |  去除所有断言和调试符号，优化性能。   |
| --- | --- |
| debug |  包含所有调试信息，适用于开发和调试，但性能较低。   |
| relassert |  不触发 `#ifdef DEBUG` 代码块，但保留调试符号，性能优于 debug。   |
| reldebug  |  类似于 relassert，但去除断言，性能更优。   |
| benchmark |  在 release 基础上启用基准测试。   |
| tidy-check |  构建后运行 Clang-Tidy 检查代码风格和潜在问题。   |
| format-fix | format-changes | format main |  使用 clang-format 和 cmake-format 检查和修复代码格式   |
| unit | debug构建后运行unittest（很慢） |


### 3.2 核心扩展
 可以通过设置 `CORE_EXTENSIONS` 变量，指定要构建的核心扩展 

```bash
CORE_EXTENSIONS='tpch;httpfs;fts;json;parquet' make
```

### 3.3 包标志（Package Flags）
用于控制是否构建特定的DuckDB包

| BUILD_PYTHON | 构建Python包 |
| --- | --- |
| BUILD_SHELL | 构建命令行界面（CLI） |
| BUILD_BENCHMARK | 构建内置基准测试套件 |
| BUILD_JDBC | 构建Java JDBC包 |
| BUILD_ODBC | 构建ODBC包 |


使用方法：在构建前通过环境变量或者命令行参数设置，例如

```bash
BUILD_PYTHON=1 make debug
```

## 4. 运行testcase
运行所有测试

```bash
#当前在duckdb根目录
./build/release/test/unittest
```

运行单个测试

```bash
#unittest文件位于build/release(或debug)/test/unittest下
#.test文件位于/test文件夹内
./build/release/test/unittest <path-to-test-file>
#eg
./build/release/test/unittest test/sql/projection/test_simple_projection.test
```

运行某目录下所有测试

```bash
./build/release/test/unittest "[<directory_name>]"
#eg 运行projection目录下测试
./build/release/test/unittest "[projection]"
```

## 5. 运行duckdb数据库
```bash
./build/release/duckdb
```

## 总结
| 安装依赖 | sudo apt-get install -y git g++ cmake ninja-build libssl-dev |
| --- | --- |
| 下载源码 | git clone [https://github.com/duckdb/duckdb.git](https://github.com/duckdb/duckdb.git) |
| 编译安装 | make debug || make release |
| 运行测试 | ./build/release(or debug)/test/unittest |
| 启用数据库 | ./build/release(or debug)/duckdb |


