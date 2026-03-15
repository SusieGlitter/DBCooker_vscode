
## 目前进度

137/503成功 2rd

## 别名函数 2nd
res0:  base64
res1:  ['./duckdb-1.3.0/extension/core_functions/include/core_functions/scalar/blob_functions.hpp', '61']
res2:  Base64Fun::(未找到GetFunction或GetFunctions)
res3:  ['']

struct ToBase64Fun {
	static constexpr const char *Name = "to_base64";
	static constexpr const char *Parameters = "blob";
	static constexpr const char *Description = "Converts a `blob` to a base64 encoded `string`.";
	static constexpr const char *Example = "base64('A'::BLOB)";
	static constexpr const char *Categories = "string,blob";

	static ScalarFunction GetFunction();
};

struct Base64Fun {
	using ALIAS = ToBase64Fun;

	static constexpr const char *Name = "base64";
};

解决方案：特判别名函数

## 非Op/Operator结尾的
AggregateFunctionSet ArgMaxFun::GetFunctions() {
	AggregateFunctionSet fun;
	AddArgMinMaxFunctions<GreaterThan, true, OrderType::DESCENDING>(fun);
	AddArgMinMaxNFunction<GreaterThan>(fun);
	return fun;
}

解决方案：遍历全部AST子结点，内容与对应函数无关（如何判断？）时剪枝

## 死循环
已解决：记忆已经搜索过的节点，避免自调用引发死循环


## 重复搜索

todo：查询上一次结果，上一次搜索成功的跳过，节约时间

## 添加描述  1st
函数的描述

## 使用understand进行查找 3rd
到getfunctions后使用understand

## 关注核心的代码（Op）1st
getfunctions是否是通用的代码

## 尝试编译源码 4th