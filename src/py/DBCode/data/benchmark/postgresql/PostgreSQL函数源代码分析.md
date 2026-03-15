## 一. 数学方程和运算符

### 1. abs

- 描述：`abs ( numeric_type ) → numeric_type`

- 函数功能：获取一个数的绝对值

- 源代码实现

  - **numeric_abs**

    - `src\backend\utils\adt\numeric.c`

      - ```c++
        Datum
        numeric_abs(PG_FUNCTION_ARGS)
        {
        	Numeric		num = PG_GETARG_NUMERIC(0);
        	Numeric		res;
        
        	/*
        	 * Do it the easy way directly on the packed format
        	 */
        	res = duplicate_numeric(num);
        
        	if (NUMERIC_IS_SHORT(num))
        		res->choice.n_short.n_header =
        			num->choice.n_short.n_header & ~NUMERIC_SHORT_SIGN_MASK;
        	else if (NUMERIC_IS_SPECIAL(num))
        	{
        		/* This changes -Inf to Inf, and doesn't affect NaN */
        		res->choice.n_short.n_header =
        			num->choice.n_short.n_header & ~NUMERIC_INF_SIGN_MASK;
        	}
        	else
        		res->choice.n_long.n_sign_dscale = NUMERIC_POS | NUMERIC_DSCALE(num);
        
        	PG_RETURN_NUMERIC(res);
        }
        ```

      - ```c++
        static Numeric
        duplicate_numeric(Numeric num)
        {
        	Numeric		res;
        
        	res = (Numeric) palloc(VARSIZE(num));
        	memcpy(res, num, VARSIZE(num));
        	return res;
        }
        ```

    - `src\include\utils\numeric.h`

      - ```c++
        static inline Numeric
        DatumGetNumeric(Datum X)
        {
        	return (Numeric) PG_DETOAST_DATUM(X);
        }
        ```

      - ```c++
        static inline Datum
        NumericGetDatum(Numeric X)
        {
        	return PointerGetDatum(X);
        }
        ```

  - **float4abs**

    - `src\backend\utils\adt\float.c`

      - ```c++
        Datum
        float4abs(PG_FUNCTION_ARGS)
        {
        	float4		arg1 = PG_GETARG_FLOAT4(0);
        
        	PG_RETURN_FLOAT4(fabsf(arg1));
        }
        ```

    - `src\include\postgres.h`

      - ```c++
        static inline Datum
        Float4GetDatum(float4 X)
        {
        	union
        	{
        		float4		value;
        		int32		retval;
        	}			myunion;
        
        	myunion.value = X;
        	return Int32GetDatum(myunion.retval);
        }
        ```

      - ```c++
        static inline float4
        DatumGetFloat4(Datum X)
        {
        	union
        	{
        		int32		value;
        		float4		retval;
        	}			myunion;
        
        	myunion.value = DatumGetInt32(X);
        	return myunion.retval;
        }
        ```

  - **float8abs**

    - `src\backend\utils\adt\float.c`

      - ```
        Datum
        float8abs(PG_FUNCTION_ARGS)
        {
        	float8		arg1 = PG_GETARG_FLOAT8(0);
        
        	PG_RETURN_FLOAT8(fabs(arg1));
        
        }
        ```

    - `src\include\postgres.h`

      - ```c++
        static inline float8
        DatumGetFloat8(Datum X)
        {
        #ifdef USE_FLOAT8_BYVAL
        	union
        	{
        		int64		value;
        		float8		retval;
        	}			myunion;
        
        	myunion.value = DatumGetInt64(X);
        	return myunion.retval;
        #else
        	return *((float8 *) DatumGetPointer(X));
        #endif
        }
        ```

    - `src\backend\utils\fmgr\fmgr.c`

      - ```c++
        Datum
        Float8GetDatum(float8 X)
        {
        	float8	   *retval = (float8 *) palloc(sizeof(float8));
        
        	*retval = X;
        	return PointerGetDatum(retval);
        }
        ```

  - **int8abs**

    - `src\backend\utils\adt\int8.c`

      - ```c++
        Datum
        int8abs(PG_FUNCTION_ARGS)
        {
        	int64		arg1 = PG_GETARG_INT64(0);
        	int64		result;
        
        	if (unlikely(arg1 == PG_INT64_MIN))
        		ereport(ERROR,
        				(errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE),
        				 errmsg("bigint out of range")));
        	result = (arg1 < 0) ? -arg1 : arg1;
        	PG_RETURN_INT64(result);
        }
        ```

    - `src\include\postgres.h`

      - ```c++
        static inline int64
        DatumGetInt64(Datum X)
        {
        #ifdef USE_FLOAT8_BYVAL
        	return (int64) X;
        #else
        	return *((int64 *) DatumGetPointer(X));
        #endif
        }
        ```

    - `src\backend\utils\fmgr\fmgr.c`

      - ```c++
        Datum
        Int64GetDatum(int64 X)
        {
        	int64	   *retval = (int64 *) palloc(sizeof(int64));
        
        	*retval = X;
        	return PointerGetDatum(retval);
        }
        ```

  - **int4abs**

    - `src\backend\utils\adt\int.c`

      - ```c++
        Datum
        int4abs(PG_FUNCTION_ARGS)
        {
        	int32		arg1 = PG_GETARG_INT32(0);
        	int32		result;
        
        	if (unlikely(arg1 == PG_INT32_MIN))
        		ereport(ERROR,
        				(errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE),
        				 errmsg("integer out of range")));
        	result = (arg1 < 0) ? -arg1 : arg1;
        	PG_RETURN_INT32(result);
        }
        ```

    - `src\include\postgres.h`

      - ```c++
        static inline Datum
        Int32GetDatum(int32 X)
        {
        	return (Datum) X;
        }
        ```

      - ```c++
        static inline int32
        DatumGetInt32(Datum X)
        {
        	return (int32) X;
        }
        ```

  - **int2abs**

    - `src\backend\utils\adt\int.c`

      - ```c++
        Datum
        int2abs(PG_FUNCTION_ARGS)
        {
        	int16		arg1 = PG_GETARG_INT16(0);
        	int16		result;
        
        	if (unlikely(arg1 == PG_INT16_MIN))
        		ereport(ERROR,
        				(errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE),
        				 errmsg("smallint out of range")));
        	result = (arg1 < 0) ? -arg1 : arg1;
        	PG_RETURN_INT16(result);
        }
        ```

    - `src\include\postgres.h`

      - ```c++
        static inline Datum
        Int16GetDatum(int16 X)
        {
        	return (Datum) X;
        }
        ```

      - ```c++
        static inline int16
        DatumGetInt16(Datum X)
        {
        	return (int16) X;
        }
        ```

### 2. cbrt

- 描述：`cbrt ( double precision ) → double precision`

- 函数功能：获取一个数的立方根

- 源代码实现

  - **dcbrt**

    - `src\backend\utils\adt\float.c`

      - ```c++
        Datum
        dcbrt(PG_FUNCTION_ARGS)
        {
        	float8		arg1 = PG_GETARG_FLOAT8(0);
        	float8		result;
        
        	result = cbrt(arg1);
        	if (unlikely(isinf(result)) && !isinf(arg1))
        		float_overflow_error();
        	if (unlikely(result == 0.0) && arg1 != 0.0)
        		float_underflow_error();
        
        	PG_RETURN_FLOAT8(result);
        }
        ```

      - ```c++
        pg_noinline void
        float_overflow_error(void)
        {
        	ereport(ERROR,
        			(errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE),
        			 errmsg("value out of range: overflow")));
        }
        ```

      - ```c++
        pg_noinline void
        float_underflow_error(void)
        {
        	ereport(ERROR,
        			(errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE),
        			 errmsg("value out of range: underflow")));
        }
        ```

    - `src\include\postgres.h`

      - ```c++
        static inline float8
        DatumGetFloat8(Datum X)
        {
        #ifdef USE_FLOAT8_BYVAL
        	union
        	{
        		int64		value;
        		float8		retval;
        	}			myunion;
        
        	myunion.value = DatumGetInt64(X);
        	return myunion.retval;
        #else
        	return *((float8 *) DatumGetPointer(X));
        #endif
        }
        ```

    - `src\backend\utils\fmgr\fmgr.c`

      - ```c++
        Datum
        Float8GetDatum(float8 X)
        {
        	float8	   *retval = (float8 *) palloc(sizeof(float8));
        
        	*retval = X;
        	return PointerGetDatum(retval);
        }
        ```

### 3. ceil

- 描述：`ceil ( numeric ) → numeric`    `ceil ( double precision ) → double precision`

- 函数功能：获取一个数的最近的大于这个数的整数

- 源代码实现

  - **dceil**

    - `src\backend\utils\adt\float.c`

      - ```c++
        Datum
        dceil(PG_FUNCTION_ARGS)
        {
        	float8		arg1 = PG_GETARG_FLOAT8(0);
        
        	PG_RETURN_FLOAT8(ceil(arg1));
        }
        ```

    - `src\include\postgres.h`

      - ```c++
        static inline float8
        DatumGetFloat8(Datum X)
        {
        #ifdef USE_FLOAT8_BYVAL
        	union
        	{
        		int64		value;
        		float8		retval;
        	}			myunion;
        
        	myunion.value = DatumGetInt64(X);
        	return myunion.retval;
        #else
        	return *((float8 *) DatumGetPointer(X));
        #endif
        }
        ```

    - `src\backend\utils\fmgr\fmgr.c`

      - ```c++
        Datum
        Float8GetDatum(float8 X)
        {
        	float8	   *retval = (float8 *) palloc(sizeof(float8));
        
        	*retval = X;
        	return PointerGetDatum(retval);
        }
        ```

  - **numeric_ceil**

    - `src\backend\utils\adt\numeric.c`

      - ```c++
        Datum
        numeric_ceil(PG_FUNCTION_ARGS)
        {
        	Numeric		num = PG_GETARG_NUMERIC(0);
        	Numeric		res;
        	NumericVar	result;
        
        	/*
        	 * Handle NaN and infinities
        	 */
        	if (NUMERIC_IS_SPECIAL(num))
        		PG_RETURN_NUMERIC(duplicate_numeric(num));
        
        	init_var_from_num(num, &result);
        	ceil_var(&result, &result);
        
        	res = make_result(&result);
        	free_var(&result);
        
        	PG_RETURN_NUMERIC(res);
        }
        ```

      - ```c++
        static Numeric
        make_result(const NumericVar *var)
        {
        	return make_result_opt_error(var, NULL);
        }
        ```

      - ```c++
        static void
        ceil_var(const NumericVar *var, NumericVar *result)
        {
        	NumericVar	tmp;
        
        	init_var(&tmp);
        	set_var_from_var(var, &tmp);
        
        	trunc_var(&tmp, 0);
        
        	if (var->sign == NUMERIC_POS && cmp_var(var, &tmp) != 0)
        		add_var(&tmp, &const_one, &tmp);
        
        	set_var_from_var(&tmp, result);
        	free_var(&tmp);
        }
        ```

      - ```c++
        static void
        free_var(NumericVar *var)
        {
        	digitbuf_free(var->buf);
        	var->buf = NULL;
        	var->digits = NULL;
        	var->sign = NUMERIC_NAN;
        }
        ```

      - ```c++
        static Numeric
        duplicate_numeric(Numeric num)
        {
        	Numeric		res;
        
        	res = (Numeric) palloc(VARSIZE(num));
        	memcpy(res, num, VARSIZE(num));
        	return res;
        }
        ```

      - ```c++
        static void
        init_var_from_num(Numeric num, NumericVar *dest)
        {
        	dest->ndigits = NUMERIC_NDIGITS(num);
        	dest->weight = NUMERIC_WEIGHT(num);
        	dest->sign = NUMERIC_SIGN(num);
        	dest->dscale = NUMERIC_DSCALE(num);
        	dest->digits = NUMERIC_DIGITS(num);
        	dest->buf = NULL;			/* digits array is not palloc'd */
        }
        ```

    - `src\include\utils\numeric.h`

      - ```c++
        static inline Datum
        NumericGetDatum(Numeric X)
        {
        	return PointerGetDatum(X);
        }
        ```

      - ```c++
        static inline Numeric
        DatumGetNumeric(Datum X)
        {
        	return (Numeric) PG_DETOAST_DATUM(X);
        }
        ```

### 4. degrees

- 描述：`degrees ( double precision ) → double precision`

- 函数功能：把弧度转为角度

- 源代码实现

  - **degrees**

    - `src\backend\utils\adt\float.c`

      - ```c++
        Datum
        degrees(PG_FUNCTION_ARGS)
        {
        	float8		arg1 = PG_GETARG_FLOAT8(0);
        
        	PG_RETURN_FLOAT8(float8_div(arg1, RADIANS_PER_DEGREE));
        }
        ```

    - `src\include\utils\float.h`

      - ```c++
        static inline float8
        float8_div(const float8 val1, const float8 val2)
        {
        	float8		result;
        
        	if (unlikely(val2 == 0.0) && !isnan(val1))
        		float_zero_divide_error();
        	result = val1 / val2;
        	if (unlikely(isinf(result)) && !isinf(val1))
        		float_overflow_error();
        	if (unlikely(result == 0.0) && val1 != 0.0 && !isinf(val2))
        		float_underflow_error();
        
        	return result;
        }
        ```

    - `src\include\postgres.h`

      - ```c++
        static inline float8
        DatumGetFloat8(Datum X)
        {
        #ifdef USE_FLOAT8_BYVAL
        	union
        	{
        		int64		value;
        		float8		retval;
        	}			myunion;
        
        	myunion.value = DatumGetInt64(X);
        	return myunion.retval;
        #else
        	return *((float8 *) DatumGetPointer(X));
        #endif
        }
        ```

    - `src\backend\utils\fmgr\fmgr.c`

      - ```c++
        Datum
        Float8GetDatum(float8 X)
        {
        	float8	   *retval = (float8 *) palloc(sizeof(float8));
        
        	*retval = X;
        	return PointerGetDatum(retval);
        }
        ```

### 5. div

- 描述：`div ( y numeric, x numeric ) → numeric`

- 函数功能：计算 y/x

- 源代码实现

  - **numeric_div_trunc**

    - `src\backend\utils\adt\numeric.c`

      - ```c++
        Datum
        numeric_div_trunc(PG_FUNCTION_ARGS)
        {
        	Numeric		num1 = PG_GETARG_NUMERIC(0);
        	Numeric		num2 = PG_GETARG_NUMERIC(1);
        	NumericVar	arg1;
        	NumericVar	arg2;
        	NumericVar	result;
        	Numeric		res;
        
        	......
        
        	/*
        	 * Do the divide and return the result
        	 */
        	div_var(&arg1, &arg2, &result, 0, false, true);
        
        	res = make_result(&result);
        
        	free_var(&result);
        
        	PG_RETURN_NUMERIC(res);
        }
        ```


      - ```c++
        static int
        numeric_sign_internal(Numeric num)
        {
        	if (NUMERIC_IS_SPECIAL(num))
        	{
        		Assert(!NUMERIC_IS_NAN(num));
        		/* Must be Inf or -Inf */
        		if (NUMERIC_IS_PINF(num))
        			return 1;
        		else
        			return -1;
        	}
        
        	/*
        	 * The packed format is known to be totally zero digit trimmed always. So
        	 * once we've eliminated specials, we can identify a zero by the fact that
        	 * there are no digits at all.
        	 */
        	else if (NUMERIC_NDIGITS(num) == 0)
        		return 0;
        	else if (NUMERIC_SIGN(num) == NUMERIC_NEG)
        		return -1;
        	else
        		return 1;
        }
        ```
    
      - ```c++
        static void
        div_var(const NumericVar *var1, const NumericVar *var2, NumericVar *result,
        		int rscale, bool round, bool exact)
        // 太长了，故省略
        ```
    
      - ```c++
        static Numeric
        make_result(const NumericVar *var)
        {
        	return make_result_opt_error(var, NULL);
        }
        ```
    
      - ```c++
        static void
        free_var(NumericVar *var)
        {
        	digitbuf_free(var->buf);
        	var->buf = NULL;
        	var->digits = NULL;
        	var->sign = NUMERIC_NAN;
        }
        ```
    
      - ```c++
        static void
        init_var_from_num(Numeric num, NumericVar *dest)
        {
        	dest->ndigits = NUMERIC_NDIGITS(num);
        	dest->weight = NUMERIC_WEIGHT(num);
        	dest->sign = NUMERIC_SIGN(num);
        	dest->dscale = NUMERIC_DSCALE(num);
        	dest->digits = NUMERIC_DIGITS(num);
        	dest->buf = NULL;			/* digits array is not palloc'd */
        }
        ```
    
    - `src\include\utils\numeric.h`
    
      - ```c++
        static inline Datum
        NumericGetDatum(Numeric X)
        {
        	return PointerGetDatum(X);
        }
        ```
    
      - ```c++
        static inline Numeric
        DatumGetNumeric(Datum X)
        {
        	return (Numeric) PG_DETOAST_DATUM(X);
        }
        ```

## 二. 字符串方程和运算符

### 1. ascii

- 描述：`ascii ( text ) → integer`

- 函数功能：获取字符串第一个字符的 ascii 码的值

- 源代码实现

  - **ascii**

    - `src\backend\utils\adt\oracle_compat.c`

      - ```c++
        Datum
        ascii(PG_FUNCTION_ARGS)
        {
        	text	   *string = PG_GETARG_TEXT_PP(0);
        	int			encoding = GetDatabaseEncoding();
        	unsigned char *data;
        
        	if (VARSIZE_ANY_EXHDR(string) <= 0)
        		PG_RETURN_INT32(0);
        
        	data = (unsigned char *) VARDATA_ANY(string);
        
        	......
        
        		PG_RETURN_INT32((int32) *data);
        	}
        }
        ```


    - `src\common\wchar.c`
    
      - ```c++
        int
        pg_encoding_max_length(int encoding)
        {
        	Assert(PG_VALID_ENCODING(encoding));
        
        	/*
        	 * Check for the encoding despite the assert, due to some mingw versions
        	 * otherwise issuing bogus warnings.
        	 */
        	return PG_VALID_ENCODING(encoding) ?
        		pg_wchar_table[encoding].maxmblen :
        		pg_wchar_table[PG_SQL_ASCII].maxmblen;
        }
        ```
    
    - `src\backend\utils\fmgr\fmgr.c`
    
      - ```c++
        struct varlena *
        pg_detoast_datum_packed(struct varlena *datum)
        {
        	if (VARATT_IS_COMPRESSED(datum) || VARATT_IS_EXTERNAL(datum))
        		return detoast_attr(datum);
        	else
        		return datum;
        }
        ```
    
    - `src\include\postgres.h`
    
      - ```c++
        static inline Pointer
        DatumGetPointer(Datum X)
        {
        	return (Pointer) X;
        }
        ```
    
      - ```c++
        static inline Datum
        Int32GetDatum(int32 X)
        {
        	return (Datum) X;
        }
        ```
    
    - `src\include\c.h`
    
      - ```c++
        struct varlena
        {
        	char		vl_len_[4];		/* Do not touch this field directly! */
        	char		vl_dat[FLEXIBLE_ARRAY_MEMBER];	/* Data content is here */
        };
        ```
    
    - `src\backend\utils\mb\mbutils.c`
    
      - ```c++
        int
        GetDatabaseEncoding(void)
        {
        	return DatabaseEncoding->encoding;
        }
        ```

### 2. chr

- 描述：`chr ( integer ) → text`

- 函数功能：把 ascii 码的值转为对应的字符

- 源代码实现

  - **chr**

    - `src\backend\utils\adt\oracle_compat.c`

      - ```c++
        Datum
        chr			(PG_FUNCTION_ARGS)
        {
        	int32		arg = PG_GETARG_INT32(0);
        	uint32		cvalue;
        	text	   *result;
        	int			encoding = GetDatabaseEncoding();
        
        	/*
        	 * Error out on arguments that make no sense or that we can't validly
        	 * represent in the encoding.
        	 */
        	if (arg < 0)
        		ereport(ERROR,
        				(errcode(ERRCODE_INVALID_PARAMETER_VALUE),
        				 errmsg("character number must be positive")));
        	else if (arg == 0)
        		ereport(ERROR,
        				(errcode(ERRCODE_PROGRAM_LIMIT_EXCEEDED),
        				 errmsg("null character not permitted")));
        
            ......
        
        	PG_RETURN_TEXT_P(result);
        }
        ```

    - `src\include\postgres.h`

      - ```c++
        static inline int32
        DatumGetInt32(Datum X)
        {
        	return (int32) X;
        }
        ```

      - ```c++
        static inline Datum
        PointerGetDatum(const void *X)
        {
        	return (Datum) X;
        }
        ```

    - `src\common\wchar.c`

      - ```c++
        bool
        pg_utf8_islegal(const unsigned char *source, int length)
        // 省略
        ```

      - ```c++
        int
        pg_encoding_max_length(int encoding)
        {
        	Assert(PG_VALID_ENCODING(encoding));
        
        	/*
        	 * Check for the encoding despite the assert, due to some mingw versions
        	 * otherwise issuing bogus warnings.
        	 */
        	return PG_VALID_ENCODING(encoding) ?
        		pg_wchar_table[encoding].maxmblen :
        		pg_wchar_table[PG_SQL_ASCII].maxmblen;
        }
        ```

    - `src\common\fe_memutils.c`

      - ```c++
        void *
        palloc(Size size)
        {
        	return pg_malloc_internal(size, 0);
        }
        ```

    - `src\backend\utils\mb\mbutils.c`

      - ```c++
        int
        GetDatabaseEncoding(void)
        {
        	return DatabaseEncoding->encoding;
        }
        ```

### 3. concat

- 描述：`concat ( val1 "any" [, val2 "any" [, ...] ] ) → text`

- 函数功能：合并所有参数为字符串

- 源代码实现

  - **text_concat**

    - `src\backend\utils\adt\varlena.c`

      - ```c++
        Datum
        text_concat(PG_FUNCTION_ARGS)
        {
        	text	   *result;
        
        	result = concat_internal("", 0, fcinfo);
        	if (result == NULL)
        		PG_RETURN_NULL();
        	PG_RETURN_TEXT_P(result);
        }
        ```

      - ```c++
        static text *
        concat_internal(const char *sepstr, int argidx,
        				FunctionCallInfo fcinfo)
        // 省略
        ```

    - `src\include\postgres.h`

      - ```c++
        static inline Datum
        PointerGetDatum(const void *X)
        {
        	return (Datum) X;
        }
        ```

### 4. concat_ws

- 描述：`concat_ws ( sep text, val1 "any" [, val2 "any" [, ...] ] ) → text`

- 函数功能：用分隔符连接除第一个参数外的所有参数。第一个参数用作分隔符字符串

- 源代码实现

  - **text_concat_ws**

    - `src\backend\utils\adt\varlena.c`

      - ```c++
        Datum
        text_concat_ws(PG_FUNCTION_ARGS)
        {
        	char	   *sep;
        	text	   *result;
        
        	/* return NULL when separator is NULL */
        	if (PG_ARGISNULL(0))
        		PG_RETURN_NULL();
        	sep = text_to_cstring(PG_GETARG_TEXT_PP(0));
        
        	result = concat_internal(sep, 1, fcinfo);
        	if (result == NULL)
        		PG_RETURN_NULL();
        	PG_RETURN_TEXT_P(result);
        }
        ```

      - ```c++
        static text *
        concat_internal(const char *sepstr, int argidx,
        				FunctionCallInfo fcinfo)
        ```

      - ```c++
        char *
        text_to_cstring(const text *t)
        {
        	/* must cast away the const, unfortunately */
        	text	   *tunpacked = pg_detoast_datum_packed(unconstify(text *, t));
        	int			len = VARSIZE_ANY_EXHDR(tunpacked);
        	char	   *result;
        
        	result = (char *) palloc(len + 1);
        	memcpy(result, VARDATA_ANY(tunpacked), len);
        	result[len] = '\0';
        
        	if (tunpacked != t)
        		pfree(tunpacked);
        
        	return result;
        }
        ```

    - `src\include\postgres.h`

      - ```c++
        static inline Datum
        PointerGetDatum(const void *X)
        {
        	return (Datum) X;
        }
        ```

      - ```c++
        static inline Pointer
        DatumGetPointer(Datum X)
        {
        	return (Pointer) X;
        }
        ```

      - `src\include\c.h`

        - ```c++
          struct varlena
          {
          	char		vl_len_[4];		/* Do not touch this field directly! */
          	char		vl_dat[FLEXIBLE_ARRAY_MEMBER];	/* Data content is here */
          };
          ```

      - `src\backend\utils\fmgr\fmgr.c`

        - ```c++
          struct varlena *
          pg_detoast_datum_packed(struct varlena *datum)
          {
          	if (VARATT_IS_COMPRESSED(datum) || VARATT_IS_EXTERNAL(datum))
          		return detoast_attr(datum);
          	else
          		return datum;
          }
          ```

### 5. format

- 描述：`format ( formatstr text [, formatarg "any" [, ...] ] ) → text`

- 函数功能：根据格式字符串格式化参数，类似于sprintf

- 源代码实现

  - **text_format**

    - `src\backend\utils\adt\varlena.c`

      - ```c++
        Datum
        text_format(PG_FUNCTION_ARGS)
        {
        	text	   *fmt;
        	StringInfoData str;
        	const char *cp;
        	const char *start_ptr;
        	const char *end_ptr;
        
            ......
            
        	/* Don't need deconstruct_array results anymore. */
        	if (elements != NULL)
        		pfree(elements);
        	if (nulls != NULL)
        		pfree(nulls);
        
        	/* Generate results. */
        	result = cstring_to_text_with_len(str.data, str.len);
        	pfree(str.data);
        
        	PG_RETURN_TEXT_P(result);
        }
        ```

      - ```c++
        text *
        cstring_to_text_with_len(const char *s, int len)
        {
        	text	   *result = (text *) palloc(len + VARHDRSZ);
        
        	SET_VARSIZE(result, len + VARHDRSZ);
        	memcpy(VARDATA(result), s, len);
        
        	return result;
        }
        ```

      - ```c++
        static const char *
        text_format_parse_format(const char *start_ptr, const char *end_ptr,
        						 int *argpos, int *widthpos,
        						 int *flags, int *width)
        // 省略
        ```

    - `src\backend\utils\fmgr\fmgr.c`

      - ```c++
        char *
        OutputFunctionCall(FmgrInfo *flinfo, Datum val)
        {
        	return DatumGetCString(FunctionCall1(flinfo, val));
        }
        ```

      - ```c++
        bool
        get_fn_expr_variadic(FmgrInfo *flinfo)
        {
        	Node	   *expr;
        
        	/*
        	 * can't return anything useful if we have no FmgrInfo or if its fn_expr
        	 * node has not been initialized
        	 */
        	if (!flinfo || !flinfo->fn_expr)
        		return false;
        
        	expr = flinfo->fn_expr;
        
        	if (IsA(expr, FuncExpr))
        		return ((FuncExpr *) expr)->funcvariadic;
        	else
        		return false;
        }
        ```

      - ```c++
        Oid
        get_fn_expr_argtype(FmgrInfo *flinfo, int argnum)
        {
        	/*
        	 * can't return anything useful if we have no FmgrInfo or if its fn_expr
        	 * node has not been initialized
        	 */
        	if (!flinfo || !flinfo->fn_expr)
        		return InvalidOid;
        
        	return get_call_expr_argtype(flinfo->fn_expr, argnum);
        }
        ```

      - ```c++
        struct varlena *
        pg_detoast_datum(struct varlena *datum)
        {
        	if (VARATT_IS_EXTENDED(datum))
        		return detoast_attr(datum);
        	else
        		return datum;
        }
        ```

      - ```c++
        void
        fmgr_info(Oid functionId, FmgrInfo *finfo)
        {
        	fmgr_info_cxt_security(functionId, finfo, CurrentMemoryContext, false);
        }
        ```

      - ```c++
        struct varlena *
        pg_detoast_datum_packed(struct varlena *datum)
        {
        	if (VARATT_IS_COMPRESSED(datum) || VARATT_IS_EXTERNAL(datum))
        		return detoast_attr(datum);
        	else
        		return datum;
        }
        ```

    - `src\common\stringinfo.c`

      - ```c++
        void
        appendStringInfoChar(StringInfo str, char ch)
        {
        	/* Make more room if needed */
        	if (str->len + 1 >= str->maxlen)
        		enlargeStringInfo(str, 1);
        
        	/* OK, append the character */
        	str->data[str->len] = ch;
        	str->len++;
        	str->data[str->len] = '\0';
        }
        ```

    - `src\backend\utils\error\elog.c`

      - ```c++
        bool
        errstart(int elevel, const char *domain)
        // 省略
        ```

      - ```c++
        void
        errfinish(const char *filename, int lineno, const char *funcname)
        // 省略
        ```

      - ```c++
        int
        errmsg_internal(const char *fmt,...)
        {
        	ErrorData  *edata = &errordata[errordata_stack_depth];
        	MemoryContext oldcontext;
        
        	recursion_depth++;
        	CHECK_STACK_DEPTH();
        	oldcontext = MemoryContextSwitchTo(edata->assoc_context);
        
        	edata->message_id = fmt;
        	EVALUATE_MESSAGE(edata->domain, message, false, false);
        
        	MemoryContextSwitchTo(oldcontext);
        	recursion_depth--;
        	return 0;					/* return value does not matter */
        }
        ```

    - `src\common\stringinfo.c`

      - ```c++
        void
        initStringInfo(StringInfo str)
        {
        	initStringInfoInternal(str, STRINGINFO_DEFAULT_SIZE);
        }
        ```

    - `src\backend\utils\cache\lsyscache.c`

      - ```c++
        void
        get_typlenbyvalalign(Oid typid, int16 *typlen, bool *typbyval,
        					 char *typalign)
        {
        	HeapTuple	tp;
        	Form_pg_type typtup;
        
        	tp = SearchSysCache1(TYPEOID, ObjectIdGetDatum(typid));
        	if (!HeapTupleIsValid(tp))
        		elog(ERROR, "cache lookup failed for type %u", typid);
        	typtup = (Form_pg_type) GETSTRUCT(tp);
        	*typlen = typtup->typlen;
        	*typbyval = typtup->typbyval;
        	*typalign = typtup->typalign;
        	ReleaseSysCache(tp);
        }
        ```

      - ```c++
        void
        getTypeOutputInfo(Oid type, Oid *typOutput, bool *typIsVarlena)
        {
        	HeapTuple	typeTuple;
        	Form_pg_type pt;
        
        	typeTuple = SearchSysCache1(TYPEOID, ObjectIdGetDatum(type));
        	if (!HeapTupleIsValid(typeTuple))
        		elog(ERROR, "cache lookup failed for type %u", type);
        	pt = (Form_pg_type) GETSTRUCT(typeTuple);
        
        	if (!pt->typisdefined)
        		ereport(ERROR,
        				(errcode(ERRCODE_UNDEFINED_OBJECT),
        				 errmsg("type %s is only a shell",
        						format_type_be(type))));
        	if (!OidIsValid(pt->typoutput))
        		ereport(ERROR,
        				(errcode(ERRCODE_UNDEFINED_FUNCTION),
        				 errmsg("no output function available for type %s",
        						format_type_be(type))));
        
        	*typOutput = pt->typoutput;
        	*typIsVarlena = (!pt->typbyval) && (pt->typlen == -1);
        
        	ReleaseSysCache(typeTuple);
        }
        ```

    - `src\backend\utils\adt\arrayfuncs.c`

      - ```c++
        void
        deconstruct_array(ArrayType *array,
        				  Oid elmtype,
        				  int elmlen, bool elmbyval, char elmalign,
        				  Datum **elemsp, bool **nullsp, int *nelemsp)
        // 省略
        ```

    - `src\common\fe_memutils.c`

      - ```c++
        void
        pfree(void *pointer)
        {
        	pg_free(pointer);
        }
        ```

    - `src\include\postgres.h`

      - ```c++
        static inline int32
        DatumGetInt32(Datum X)
        {
        	return (int32) X;
        }
        ```

      - ```c++
        static inline int16
        DatumGetInt16(Datum X)
        {
        	return (int16) X;
        }
        ```

      - ```c++
        static inline Pointer
        DatumGetPointer(Datum X)
        {
        	return (Pointer) X;
        }
        ```

      - ```c++
        static inline Datum
        PointerGetDatum(const void *X)
        {
        	return (Datum) X;
        }
        ```

    - `src\include\c.h`

      - ```c++
        struct varlena
        {
        	char		vl_len_[4];		/* Do not touch this field directly! */
        	char		vl_dat[FLEXIBLE_ARRAY_MEMBER];	/* Data content is here */
        };
        ```

    - `src\backend\utils\adt\numutils.c`

      - ```c++
        int32
        pg_strtoint32(const char *s)
        {
        	return pg_strtoint32_safe(s, NULL);
        }
        ```

  - **text_format_nv**

    - `src\backend\utils\adt\varlena.c`

      - ```c++
        Datum
        text_format_nv(PG_FUNCTION_ARGS)
        {
        	return text_format(fcinfo);
        }
        ```

      - ```c++
        Datum
        text_format(PG_FUNCTION_ARGS)
        // 省略，就是上面那个函数，text_format_nv 封装了这个函数
        ```

## 三.模式匹配

### 1. like

- 描述：`string LIKE pattern [ESCAPE escape-character]`

- 函数功能：字符串模式匹配（通配符）

- 源代码实现

  - `src\backend\utils\adt\like.c`

    - ```c++
      Datum
      textlike(PG_FUNCTION_ARGS)
      {
      	text	   *str = PG_GETARG_TEXT_PP(0);
      	text	   *pat = PG_GETARG_TEXT_PP(1);
      	bool		result;
      	char	   *s,
      			   *p;
      	int			slen,
      				plen;
      
      	s = VARDATA_ANY(str);
      	slen = VARSIZE_ANY_EXHDR(str);
      	p = VARDATA_ANY(pat);
      	plen = VARSIZE_ANY_EXHDR(pat);
      
      	result = (GenericMatchText(s, slen, p, plen, PG_GET_COLLATION()) == LIKE_TRUE);
      
      	PG_RETURN_BOOL(result);
      }
      ```

    - ```c++
      Datum
      namelike(PG_FUNCTION_ARGS)
      {
      	Name		str = PG_GETARG_NAME(0);
      	text	   *pat = PG_GETARG_TEXT_PP(1);
      	bool		result;
      	char	   *s,
      			   *p;
      	int			slen,
      				plen;
      
      	s = NameStr(*str);
      	slen = strlen(s);
      	p = VARDATA_ANY(pat);
      	plen = VARSIZE_ANY_EXHDR(pat);
      
      	result = (GenericMatchText(s, slen, p, plen, PG_GET_COLLATION()) == LIKE_TRUE);
      
      	PG_RETURN_BOOL(result);
      }
      ```

    - ```c++
      Datum
      bytealike(PG_FUNCTION_ARGS)
      {
      	bytea	   *str = PG_GETARG_BYTEA_PP(0);
      	bytea	   *pat = PG_GETARG_BYTEA_PP(1);
      	bool		result;
      	char	   *s,
      			   *p;
      	int			slen,
      				plen;
      
      	s = VARDATA_ANY(str);
      	slen = VARSIZE_ANY_EXHDR(str);
      	p = VARDATA_ANY(pat);
      	plen = VARSIZE_ANY_EXHDR(pat);
      
      	result = (SB_MatchText(s, slen, p, plen, 0) == LIKE_TRUE);
      
      	PG_RETURN_BOOL(result);
      }
      ```

### 2. similar to

- 描述：`string SIMILAR TO pattern [ESCAPE escape-character]`

- 函数功能：字符串模式匹配（正则表达式）

- 源代码实现

  - `src\backend\utils\adt\regexp.c`

    - ```c++
      Datum
      similar_to_escape_2(PG_FUNCTION_ARGS)
      {
      	text	   *pat_text = PG_GETARG_TEXT_PP(0);
      	text	   *esc_text = PG_GETARG_TEXT_PP(1);
      	text	   *result;
      
      	result = similar_escape_internal(pat_text, esc_text);
      
      	PG_RETURN_TEXT_P(result);
      }
      ```

    - ```c++
      Datum
      similar_to_escape_1(PG_FUNCTION_ARGS)
      {
      	text	   *pat_text = PG_GETARG_TEXT_PP(0);
      	text	   *result;
      
      	result = similar_escape_internal(pat_text, NULL);
      
      	PG_RETURN_TEXT_P(result);
      }
      ```

    - ```c++
      Datum
      similar_escape(PG_FUNCTION_ARGS)
      {
      	text	   *pat_text;
      	text	   *esc_text;
      	text	   *result;
      
      	/* This function is not strict, so must test explicitly */
      	if (PG_ARGISNULL(0))
      		PG_RETURN_NULL();
      	pat_text = PG_GETARG_TEXT_PP(0);
      
      	if (PG_ARGISNULL(1))
      		esc_text = NULL;		/* use default escape character */
      	else
      		esc_text = PG_GETARG_TEXT_PP(1);
      
      	result = similar_escape_internal(pat_text, esc_text);
      
      	PG_RETURN_TEXT_P(result);
      }
      ```

### 3. regexp_like

- 描述：`regexp_like ( string text, pattern text [, flags text ] ) → boolean`

- 函数功能：字符串完整正则表达式匹配

- 源代码实现

  - `src\backend\utils\adt\regexp.c`

    - ```c++
      Datum
      regexp_like_no_flags(PG_FUNCTION_ARGS)
      {
      	return regexp_like(fcinfo);
      }
      ```

    - ```c++
      Datum
      regexp_like(PG_FUNCTION_ARGS)
      {
      	text	   *str = PG_GETARG_TEXT_PP(0);
      	text	   *pattern = PG_GETARG_TEXT_PP(1);
      	text	   *flags = PG_GETARG_TEXT_PP_IF_EXISTS(2);
      	pg_re_flags re_flags;
      
      	/* Determine options */
      	parse_re_flags(&re_flags, flags);
      	/* User mustn't specify 'g' */
      	if (re_flags.glob)
      		ereport(ERROR,
      				(errcode(ERRCODE_INVALID_PARAMETER_VALUE),
      		/* translator: %s is a SQL function name */
      				 errmsg("%s does not support the \"global\" option",
      						"regexp_like()")));
      
      	/* Otherwise it's like textregexeq/texticregexeq */
      	PG_RETURN_BOOL(RE_compile_and_execute(pattern,
      										  VARDATA_ANY(str),
      										  VARSIZE_ANY_EXHDR(str),
      										  re_flags.cflags,
      										  PG_GET_COLLATION(),
      										  0, NULL));
      }
      ```



## 四.数据类型转换

### 1. to_char（多种模式，仅举例一种）

- 描述：`to_char ( numeric_type, ) → text text`   

- 函数功能：把各种数据类型转为字符串

- 源代码实现

  - `src\backend\utils\adt\formatting.c`

    - ```c++
      Datum
      numeric_to_char(PG_FUNCTION_ARGS)
      {
      	Numeric		value = PG_GETARG_NUMERIC(0);
      	text	   *fmt = PG_GETARG_TEXT_PP(1);
      	NUMDesc		Num;
      	FormatNode *format;
      	text	   *result;
      	bool		shouldFree;
      	int			out_pre_spaces = 0,
      				sign = 0;
      	char	   *numstr,
      			   *orgnum,
      			   *p;
      
      	NUM_TOCHAR_prepare;
      
      	......
      
      	NUM_TOCHAR_finish;
      	PG_RETURN_TEXT_P(result);
      }
      ```

### 2. to_date

- 描述：`to_date ( text, ) → textdate`

- 函数功能：把字符串转为给定格式的日期

- 源代码实现

  - `src\backend\utils\adt\formatting.c`

    - ```c++
      Datum
      to_date(PG_FUNCTION_ARGS)
      {
      	text	   *date_txt = PG_GETARG_TEXT_PP(0);
      	text	   *fmt = PG_GETARG_TEXT_PP(1);
      	Oid			collid = PG_GET_COLLATION();
      	DateADT		result;
      	struct pg_tm tm;
      	struct fmt_tz ftz;
      	fsec_t		fsec;
      
      	do_to_timestamp(date_txt, fmt, collid, false,
      					&tm, &fsec, &ftz, NULL, NULL, NULL);
      
      	/* Prevent overflow in Julian-day routines */
      	if (!IS_VALID_JULIAN(tm.tm_year, tm.tm_mon, tm.tm_mday))
      		ereport(ERROR,
      				(errcode(ERRCODE_DATETIME_VALUE_OUT_OF_RANGE),
      				 errmsg("date out of range: \"%s\"",
      						text_to_cstring(date_txt))));
      
      	result = date2j(tm.tm_year, tm.tm_mon, tm.tm_mday) - POSTGRES_EPOCH_JDATE;
      
      	/* Now check for just-out-of-range dates */
      	if (!IS_VALID_DATE(result))
      		ereport(ERROR,
      				(errcode(ERRCODE_DATETIME_VALUE_OUT_OF_RANGE),
      				 errmsg("date out of range: \"%s\"",
      						text_to_cstring(date_txt))));
      
      	PG_RETURN_DATEADT(result);
      }
      ```

### 3. to_number

- 描述：`to_number ( text, ) → text numeric`

- 函数功能：把字符串转为给定格式的数字

- 源代码实现

  - `src\backend\utils\adt\formatting.c`

    - ```c++
      Datum
      numeric_to_number(PG_FUNCTION_ARGS)
      {
      	text	   *value = PG_GETARG_TEXT_PP(0);
      	text	   *fmt = PG_GETARG_TEXT_PP(1);
      	NUMDesc		Num;
      	Datum		result;
      	FormatNode *format;
      	char	   *numstr;
      	bool		shouldFree;
      	int			len = 0;
      	int			scale,
      				precision;
      
      	len = VARSIZE_ANY_EXHDR(fmt);
      
      	if (len <= 0 || len >= INT_MAX / NUM_MAX_ITEM_SIZ)
      		PG_RETURN_NULL();
      
      	format = NUM_cache(len, &Num, fmt, &shouldFree);
      
      	numstr = (char *) palloc((len * NUM_MAX_ITEM_SIZ) + 1);
      
      	NUM_processor(format, &Num, VARDATA_ANY(value), numstr,
      				  VARSIZE_ANY_EXHDR(value), 0, 0, false, PG_GET_COLLATION());
      
      	scale = Num.post;
      	precision = Num.pre + Num.multi + scale;
      
      	if (shouldFree)
      		pfree(format);
      
      	result = DirectFunctionCall3(numeric_in,
      								 CStringGetDatum(numstr),
      								 ObjectIdGetDatum(InvalidOid),
      								 Int32GetDatum(((precision << 16) | scale) + VARHDRSZ));
      
      	if (IS_MULTI(&Num))
      	{
      		Numeric		x;
      		Numeric		a = int64_to_numeric(10);
      		Numeric		b = int64_to_numeric(-Num.multi);
      
      		x = DatumGetNumeric(DirectFunctionCall2(numeric_power,
      												NumericGetDatum(a),
      												NumericGetDatum(b)));
      		result = DirectFunctionCall2(numeric_mul,
      									 result,
      									 NumericGetDatum(x));
      	}
      
      	pfree(numstr);
      	return result;
      }
      ```



## 五.日期时间函数

### 1. age

- 描述：`age ( timestamp, timestamp ) → interval`

- 函数功能：计算时间差（年月格式）

- 源代码描述

  - `src\backend\utils\adt\timestamp.c`

  - ```c++
    Datum
    timestamp_age(PG_FUNCTION_ARGS)
    {
    	Timestamp	dt1 = PG_GETARG_TIMESTAMP(0);
    	Timestamp	dt2 = PG_GETARG_TIMESTAMP(1);
    	Interval   *result;
    	fsec_t		fsec1,
    				fsec2;
    	struct pg_itm tt,
    			   *tm = &tt;
    	struct pg_tm tt1,
    			   *tm1 = &tt1;
    	struct pg_tm tt2,
    			   *tm2 = &tt2;
    
    	result = (Interval *) palloc(sizeof(Interval));
    
    	......
    
    	PG_RETURN_INTERVAL_P(result);
    }
    ```

### 2. clock_timestamp

- 描述：`clock_timestamp ( ) → timestamp with time zone`

- 函数功能：获取当前日期和时间

- 源代码实现

  - `src\backend\utils\adt\timestamp.c`

    - ```c++
      Datum
      clock_timestamp(PG_FUNCTION_ARGS)
      {
      	PG_RETURN_TIMESTAMPTZ(GetCurrentTimestamp());
      }
      ```

### 3. justify_hours

- 描述：`justify_hours ( interval ) → interval`

- 函数功能：把 小时-分钟 转为 天-小时-分钟

- 源代码实现

  - `src\backend\utils\adt\timestamp.c`

    - ```c++
      Datum
      interval_justify_hours(PG_FUNCTION_ARGS)
      {
      	Interval   *span = PG_GETARG_INTERVAL_P(0);
      	Interval   *result;
      	TimeOffset	wholeday;
      
      	result = (Interval *) palloc(sizeof(Interval));
      	result->month = span->month;
      	result->day = span->day;
      	result->time = span->time;
      
      	/* do nothing for infinite intervals */
      	if (INTERVAL_NOT_FINITE(result))
      		PG_RETURN_INTERVAL_P(result);
      
      	TMODULO(result->time, wholeday, USECS_PER_DAY);
      	if (pg_add_s32_overflow(result->day, wholeday, &result->day))
      		ereport(ERROR,
      				(errcode(ERRCODE_DATETIME_VALUE_OUT_OF_RANGE),
      				 errmsg("interval out of range")));
      
      	if (result->day > 0 && result->time < 0)
      	{
      		result->time += USECS_PER_DAY;
      		result->day--;
      	}
      	else if (result->day < 0 && result->time > 0)
      	{
      		result->time -= USECS_PER_DAY;
      		result->day++;
      	}
      
      	PG_RETURN_INTERVAL_P(result);
      }
      ```

      





























