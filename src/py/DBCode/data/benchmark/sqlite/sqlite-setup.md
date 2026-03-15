## 下载sqlite源码
```bash
https://github.com/sqlite/sqlite.git
cd sqlite
```

## 编译安装
```bash
mkdir build
cd build #进入到隔离文件夹
../sqlite/configure #加载配置
make sqlite3
make tclextension-install # TCL extension
make sqlite3_analyzer #  Builds the "sqlite3_analyzer" tool
```

## 测试
### 批量测试
下面的测试可任选

```bash
make devtest # 开发测试（srctree-check+源码检查）
make releasetest # 发行测试（不包含srctree-check和源码检查）
make quicktest # 快速测试（包含部分tcl测试，不包含异常、模糊和侵泡测试）
make tcltest # tcl测试
```

### 单条tcl测试
```bash
# 单条tcl测试准备
make testfixture # build testfixture - an TCL interpreter
# 运行单条tcl测试
testfixture <path to .test file>
#eg.
testfixture test/xxx.test
```

