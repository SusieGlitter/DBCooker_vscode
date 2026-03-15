## 一. 数学方程和运算符

### 1. abs

- 描述：`abs ( numeric_type ) → numeric_type`

- 函数功能：获取一个数的绝对值

- 源代码实现

  - **numeric_abs**

    - `src\include\c.h`

      - ```c++
        struct varlena
        {
        	char		vl_len_[4];		/* Do not touch this field directly! */
        	char		vl_dat[FLEXIBLE_ARRAY_MEMBER];	/* Data content is here */
        };
        ```

    - `src\include\fmgr.h`

      - ```c++
        #define PG_DETOAST_DATUM pg_detoast_datum((struct varlena *) DatumGetPointer(datum))
        #define PG_FUNCTION_ARGS FunctionCallInfo fcinfo
        #define PG_GETARG_DATUM (fcinfo->arg[n])
        ```

    - `src\backend\utils\fmgr\fmgr.c`

      - ```c++
        struct varlena *
        pg_detoast_datum(struct varlena * datum)
        {
        	if (VARATT_IS_EXTENDED(datum))
        		return heap_tuple_untoast_attr(datum);
        	else
        		return datum;
        }
        ```

    - `src\include\postgres.h`

      - ```c++
        #define DatumGetPointer ((Pointer) (X))
        #define PointerGetDatum ((Datum) (X))
        #define VARSIZE VARSIZE_4B(PTR)
        #define VARSIZE_4B ((((varattrib_4b *) (PTR))->va_4byte.va_header >> 2) & 0x3FFFFFFF)
        ```

    - `src\common\fe_memutils.c`

      - ```c++
        void *
        palloc(Size size)
        {
        	return pg_malloc_internal(size, 0);
        }
        ```

    - `src\include\utils\numeric.h`

      - ```c++
        #define DatumGetNumeric ((Numeric) PG_DETOAST_DATUM(X))
        #define NumericGetDatum PointerGetDatum(X)
        #define PG_GETARG_NUMERIC DatumGetNumeric(PG_GETARG_DATUM(n))
        #define PG_RETURN_NUMERIC return NumericGetDatum(x)
        ```

    - `src\backend\utils\adt\numeric.c`

      - ```c++
        #define NUMERIC_DSCALE (NUMERIC_HEADER_IS_SHORT((n)) ? ((n)->choice.n_short.n_header & NUMERIC_SHORT_DSCALE_MASK) >> NUMERIC_SHORT_DSCALE_SHIFT : ((n)->choice.n_long.n_sign_dscale & NUMERIC_DSCALE_MASK))
        #define NUMERIC_DSCALE_MASK 0x3FFF
        #define NUMERIC_FLAGBITS ((n)->choice.n_header & NUMERIC_SIGN_MASK)
        
        // 省略
        
        	dump_numeric("make_result()", result);
        	return result;
        }
        ```

    - `src\interfaces\ecpg\test\expected\sql-sqlda.c`

      - ```c++
        #define NUMERIC_NAN 0xC000
        #define NUMERIC_POS 0x0000
        ```

    - `src\backend\utils\adt\numeric.c`

      - ```c++
        Datum
        numeric_abs(PG_FUNCTION_ARGS)
        {
        	Numeric		num = PG_GETARG_NUMERIC(0);
        	Numeric		res;
        
        	/*
        	 * Handle NaN
        	 */
        	if (NUMERIC_IS_NAN(num))
        		PG_RETURN_NUMERIC(make_result(&const_nan));
        
        	/*
        	 * Do it the easy way directly on the packed format
        	 */
        	res = (Numeric) palloc(VARSIZE(num));
        	memcpy(res, num, VARSIZE(num));
        
        	if (NUMERIC_IS_SHORT(num))
        		res->choice.n_short.n_header =
        			num->choice.n_short.n_header & ~NUMERIC_SHORT_SIGN_MASK;
        	else
        		res->choice.n_long.n_sign_dscale = NUMERIC_POS | NUMERIC_DSCALE(num);
        
        	PG_RETURN_NUMERIC(res);
        }
        ```

  - **float4abs**

    - `src\include\fmgr.h`

      - ```c++
        #define PG_FUNCTION_ARGS FunctionCallInfo fcinfo
        #define PG_GETARG_DATUM (fcinfo->arg[n])
        #define PG_GETARG_FLOAT4 DatumGetFloat4(PG_GETARG_DATUM(n))
        #define PG_RETURN_FLOAT4 return Float4GetDatum(x)
        ```

    - `src\include\postgres.h`

      - ```c++
        #define DatumGetFloat4 (* ((float4 *) DatumGetPointer(X)))
        #define DatumGetPointer ((Pointer) (X))
        ```

    - `src\backend\utils\fmgr\fmgr.c`

      - ```c++
        Datum
        Float4GetDatum(float4 X)
        {
        #ifdef USE_FLOAT4_BYVAL
        	union
        	{
        		float4		value;
        		int32		retval;
        	}			myunion;
        
        	myunion.value = X;
        	return SET_4_BYTES(myunion.retval);
        #else
        	float4	   *retval = (float4 *) palloc(sizeof(float4));
        
        	*retval = X;
        	return PointerGetDatum(retval);
        #endif
        }
        ```

    - `src\backend\utils\adt\float.c`

      - ```c++
        Datum
        float4abs(PG_FUNCTION_ARGS)
        {
        	float4		arg1 = PG_GETARG_FLOAT4(0);
        
        	PG_RETURN_FLOAT4((float4) fabs(arg1));
        }
        ```

  - **float8abs**

    - `src\include\fmgr.h`

      - ```
        #define PG_FUNCTION_ARGS FunctionCallInfo fcinfo
        #define PG_GETARG_DATUM (fcinfo->arg[n])
        #define PG_GETARG_FLOAT8 DatumGetFloat8(PG_GETARG_DATUM(n))
        #define PG_RETURN_FLOAT8 return Float8GetDatum(x)
        ```

    - `src\include\postgres.h`

      - ```c++
        #define DatumGetFloat8 (* ((float8 *) DatumGetPointer(X)))
        #define DatumGetPointer ((Pointer) (X))
        ```

    - `src\backend\utils\fmgr\fmgr.c`

      - ```c++
        Datum
        Float8GetDatum(float8 X)
        {
        #ifdef USE_FLOAT8_BYVAL
        	union
        	{
        		float8		value;
        		int64		retval;
        	}			myunion;
        
        	myunion.value = X;
        	return SET_8_BYTES(myunion.retval);
        #else
        	float8	   *retval = (float8 *) palloc(sizeof(float8));
        
        	*retval = X;
        	return PointerGetDatum(retval);
        #endif
        }
        ```

    - `src\backend\utils\adt\float.c`

      - ```c++
        Datum
        float8abs(PG_FUNCTION_ARGS)
        {
        	float8		arg1 = PG_GETARG_FLOAT8(0);
        
        	PG_RETURN_FLOAT8(fabs(arg1));
        }
        ```

  - **int8abs**

    - `src\include\c.h`

      - ```c++
        #define pg_unreachable __assume(0)
        ```

    - `src\include\fmgr.h`

      - ```c++
        #define PG_FUNCTION_ARGS FunctionCallInfo fcinfo
        #define PG_GETARG_DATUM (fcinfo->arg[n])
        #define PG_GETARG_INT64 DatumGetInt64(PG_GETARG_DATUM(n))
        #define PG_RETURN_INT64 return Int64GetDatum(x)
        ```

    - `src\include\postgres.h`

      - ```c++
        #define DatumGetInt64 (* ((int64 *) DatumGetPointer(X)))
        #define DatumGetPointer ((Pointer) (X))
        ```

    - `src\include\utils\elog.h`

      - ```c++
        #define ERROR 20
        #define PG_FUNCNAME_MACRO NULL
        #define TEXTDOMAIN NULL
        #define ereport ereport_domain(elevel, TEXTDOMAIN, rest)
        #define ereport_domain do { const int elevel_ = (elevel); if (errstart(elevel_, __FILE__, __LINE__, PG_FUNCNAME_MACRO, domain)) errfinish rest; if (elevel_ >= ERROR) pg_unreachable(); } while(0)
        ```

    - `src\backend\utils\adt\int8.c`

      - ```c++
        Datum
        int8abs(PG_FUNCTION_ARGS)
        {
        	int64		arg1 = PG_GETARG_INT64(0);
      	int64		result;
        
      	result = (arg1 < 0) ? -arg1 : arg1;
        	/* overflow check (needed for INT64_MIN) */
        	if (result < 0)
        		ereport(ERROR,
        				(errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE),
        				 errmsg("bigint out of range")));
        	PG_RETURN_INT64(result);
        }
        ```
    
  - **int4abs**
  
    - `src\include\c.h`
  
      - ```c++
        #define pg_unreachable __assume(0)
        ```

    - `src\include\fmgr.h`

      - ```c++
      #define PG_FUNCTION_ARGS FunctionCallInfo fcinfo
        #define PG_GETARG_DATUM (fcinfo->arg[n])
        #define PG_GETARG_INT32 DatumGetInt32(PG_GETARG_DATUM(n))
        #define PG_RETURN_INT32 return Int32GetDatum(x)
      ```
  
  - `src\include\postgres.h`
  
      - ```c++
        #define DatumGetInt32 ((int32) GET_4_BYTES(X))
        #define GET_4_BYTES (((Datum) (datum)) & 0xffffffff)
        #define Int32GetDatum ((Datum) SET_4_BYTES(X))
        #define SET_4_BYTES (((Datum) (value)) & 0xffffffff)
      ```
  
  - `src\include\utils\elog.h`
  
      - ```c++
        #define ERROR 20
        #define PG_FUNCNAME_MACRO NULL
        #define TEXTDOMAIN NULL
        #define ereport ereport_domain(elevel, TEXTDOMAIN, rest)
      #define ereport_domain do { const int elevel_ = (elevel); if (errstart(elevel_, __FILE__, __LINE__, PG_FUNCNAME_MACRO, domain)) errfinish rest; if (elevel_ >= ERROR) pg_unreachable(); } while(0)
        ```

    - `src\backend\utils\adt\int.c`
  
      - ```c++
        Datum
        int4abs(PG_FUNCTION_ARGS)
        {
        	int32		arg1 = PG_GETARG_INT32(0);
      	int32		result;
        
      	result = (arg1 < 0) ? -arg1 : arg1;
        	/* overflow check (needed for INT_MIN) */
        	if (result < 0)
        		ereport(ERROR,
        				(errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE),
        				 errmsg("integer out of range")));
      	PG_RETURN_INT32(result);
        }
      ```
    
  - **int2abs**
  
    - `src\include\c.h`
  
      - ```c++
        #define pg_unreachable __assume(0)
        ```
  
    - `src\include\fmgr.h`
  
      - ```c++
        #define PG_FUNCTION_ARGS FunctionCallInfo fcinfo
        #define PG_GETARG_DATUM (fcinfo->arg[n])
        #define PG_GETARG_INT16 DatumGetInt16(PG_GETARG_DATUM(n))
        #define PG_RETURN_INT16 return Int16GetDatum(x)
      ```
  
  - `src\include\postgres.h`
  
    - ```c++
        #define DatumGetInt16 ((int16) GET_2_BYTES(X))
        #define GET_2_BYTES (((Datum) (datum)) & 0x0000ffff)
        #define Int16GetDatum ((Datum) SET_2_BYTES(X))
      #define SET_2_BYTES (((Datum) (value)) & 0x0000ffff)
        ```

    - `src\include\utils\elog.h`
  
      - ```c++
        #define ERROR 20
        #define PG_FUNCNAME_MACRO NULL
        #define TEXTDOMAIN NULL
      #define ereport ereport_domain(elevel, TEXTDOMAIN, rest)
        #define ereport_domain do { const int elevel_ = (elevel); if (errstart(elevel_, __FILE__, __LINE__, PG_FUNCNAME_MACRO, domain)) errfinish rest; if (elevel_ >= ERROR) pg_unreachable(); } while(0)
      ```
  
    - `src\backend\utils\adt\int.c`
  
      - ```c++
        Datum
        int2abs(PG_FUNCTION_ARGS)
      {
        	int16		arg1 = PG_GETARG_INT16(0);
      	int16		result;
        
        	result = (arg1 < 0) ? -arg1 : arg1;
        	/* overflow check (needed for SHRT_MIN) */
        	if (result < 0)
        		ereport(ERROR,
        				(errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE),
        				 errmsg("smallint out of range")));
      	PG_RETURN_INT16(result);
        }
      ```

### 2. cbrt

- 描述：`cbrt ( double precision ) → double precision`

- 函数功能：获取一个数的立方根

- 源代码实现

  - **dcbrt**

    - `src\backend\utils\adt\float.c`

      - ```c++
        #define CHECKFLOATVAL do { if (isinf(val) && !(inf_is_valid)) ereport(ERROR, (errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE), errmsg("value out of range: overflow"))); if ((val) == 0.0 && !(zero_is_valid)) ereport(ERROR, (errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE), errmsg("value out of range: underflow"))); } while(0)
        #define cbrt my_cbrt
        static double
        cbrt(double x)
        {
        	int			isneg = (x < 0.0);
        	double		absx = fabs(x);
        	double		tmpres = pow(absx, (double) 1.0 / (double) 3.0);
        
        	/*
        	 * The result is somewhat inaccurate --- not really pow()'s fault, as the
        	 * exponent it's handed contains roundoff error.  We can improve the
        	 * accuracy by doing one iteration of Newton's formula.  Beware of zero
        	 * input however.
        	 */
        	if (tmpres > 0.0)
        		tmpres -= (tmpres - absx / (tmpres * tmpres)) / (double) 3.0;
        
        	return isneg ? -tmpres : tmpres;
        }
        ```

    - `src\include\c.h`

      - ```c++
        #define pg_unreachable __assume(0)
        ```

    - `src\include\fmgr.h`

      - ```c++
        #define PG_FUNCTION_ARGS FunctionCallInfo fcinfo
        #define PG_GETARG_DATUM (fcinfo->arg[n])
        #define PG_GETARG_FLOAT8 DatumGetFloat8(PG_GETARG_DATUM(n))
        #define PG_RETURN_FLOAT8 return Float8GetDatum(x)
        ```

    - `src\include\postgres.h`

      - ```c++
        #define DatumGetFloat8 (* ((float8 *) DatumGetPointer(X)))
        #define DatumGetPointer ((Pointer) (X))
        ```

    - `src\backend\utils\fmgr\fmgr.c`

      - ```c+
        Datum
        Float8GetDatum(float8 X)
        {
        #ifdef USE_FLOAT8_BYVAL
        	union
        	{
        		float8		value;
        		int64		retval;
        	}			myunion;
        
        	myunion.value = X;
        	return SET_8_BYTES(myunion.retval);
        #else
        	float8	   *retval = (float8 *) palloc(sizeof(float8));
        
        	*retval = X;
        	return PointerGetDatum(retval);
        #endif
        }
        ```

    - `src\include\utils\elog.h`

      - ```c++
        #define ERROR 20
        #define PG_FUNCNAME_MACRO NULL
        #define TEXTDOMAIN NULL
        #define ereport ereport_domain(elevel, TEXTDOMAIN, rest)
        #define ereport_domain do { const int elevel_ = (elevel); if (errstart(elevel_, __FILE__, __LINE__, PG_FUNCNAME_MACRO, domain)) errfinish rest; if (elevel_ >= ERROR) pg_unreachable(); } while(0)
        ```

    - `src\backend\utils\adt\float.c`

      - ```c++
        Datum
        dcbrt(PG_FUNCTION_ARGS)
        {
        	float8		arg1 = PG_GETARG_FLOAT8(0);
        	float8		result;
        
        	result = cbrt(arg1);
        	CHECKFLOATVAL(result, isinf(arg1), arg1 == 0);
        	PG_RETURN_FLOAT8(result);
        }
        ```

### 3. ceil

- 描述：`ceil ( numeric ) → numeric`    `ceil ( double precision ) → double precision`

- 函数功能：获取一个数的最近的大于这个数的整数

- 源代码实现

  - **dceil**

    - `src\include\fmgr.h`

      - ```c++
        #define PG_FUNCTION_ARGS FunctionCallInfo fcinfo
        #define PG_GETARG_DATUM (fcinfo->arg[n])
        #define PG_GETARG_FLOAT8 DatumGetFloat8(PG_GETARG_DATUM(n))
        #define PG_RETURN_FLOAT8 return Float8GetDatum(x)
        ```

    - `src\include\postgres.h`

      - ```c++
        #define DatumGetFloat8 (* ((float8 *) DatumGetPointer(X)))
        #define DatumGetPointer ((Pointer) (X))
        ```

    - `src\backend\utils\fmgr\fmgr.c`

      - ```c++
        Datum
        Float8GetDatum(float8 X)
        {
        #ifdef USE_FLOAT8_BYVAL
        	union
        	{
        		float8		value;
        		int64		retval;
        	}			myunion;
        
        	myunion.value = X;
        	return SET_8_BYTES(myunion.retval);
        #else
        	float8	   *retval = (float8 *) palloc(sizeof(float8));
        
        	*retval = X;
        	return PointerGetDatum(retval);
        #endif
        }
        ```

    - `src\backend\utils\adt\float.c`

      - ```c++
        Datum
        dceil(PG_FUNCTION_ARGS)
        {
        	float8		arg1 = PG_GETARG_FLOAT8(0);
        
        	PG_RETURN_FLOAT8(ceil(arg1));
        }
        ```

  - **numeric_ceil**

    - `src\include\c.h`

      - ```c++
        struct varlena
        {
        	char		vl_len_[4];		/* Do not touch this field directly! */
        	char		vl_dat[FLEXIBLE_ARRAY_MEMBER];	/* Data content is here */
        };
        ```

    - `src\include\fmgr.h`

      - ```c++
        #define PG_DETOAST_DATUM pg_detoast_datum((struct varlena *) DatumGetPointer(datum))
        #define PG_FUNCTION_ARGS FunctionCallInfo fcinfo
        #define PG_GETARG_DATUM (fcinfo->arg[n])
        ```

    - `src\backend\utils\fmgr\fmgr.c`

      - ```c++
        struct varlena *
        pg_detoast_datum(struct varlena * datum)
        {
        	if (VARATT_IS_EXTENDED(datum))
        		return heap_tuple_untoast_attr(datum);
        	else
        		return datum;
        }
        ```

    - `src\include\postgres.h`

      - ```c++
        #define DatumGetPointer ((Pointer) (X))
        #define PointerGetDatum ((Datum) (X))
        ```

    - `src\include\utils\numeric.h`

      - ```c++
        #define DatumGetNumeric ((Numeric) PG_DETOAST_DATUM(X))
        #define NumericGetDatum PointerGetDatum(X)
        #define PG_GETARG_NUMERIC DatumGetNumeric(PG_GETARG_DATUM(n))
        #define PG_RETURN_NUMERIC return NumericGetDatum(x)
        ```

    - `src\backend\utils\adt\numeric.c`

      - ```c++
        #define NUMERIC_FLAGBITS ((n)->choice.n_header & NUMERIC_SIGN_MASK)
        #define NUMERIC_IS_NAN (NUMERIC_FLAGBITS(n) == NUMERIC_NAN)
        #define NUMERIC_SIGN_MASK 0xC000
        static void
        ceil_var(NumericVar *var, NumericVar *result)
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
        static void
        free_var(NumericVar *var)
        {
        	digitbuf_free(var->buf);
        	var->buf = NULL;
        	var->digits = NULL;
        	var->sign = NUMERIC_NAN;
        }
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
        static Numeric
        make_result(NumericVar *var)
        {
        // 省略
        }
        ```

    - `src\interfaces\ecpg\test\expected\sql-sqlda.c`

      - ```c++
        #define NUMERIC_NAN 0xC000
        ```

    - `src\backend\utils\adt\numeric.c`

      - ```c++
        Datum
        numeric_ceil(PG_FUNCTION_ARGS)
        {
        	Numeric		num = PG_GETARG_NUMERIC(0);
        	Numeric		res;
        	NumericVar	result;
        
        	if (NUMERIC_IS_NAN(num))
        		PG_RETURN_NUMERIC(make_result(&const_nan));
        
        	init_var_from_num(num, &result);
        	ceil_var(&result, &result);
        
        	res = make_result(&result);
        	free_var(&result);
        
        	PG_RETURN_NUMERIC(res);
        }
        ```

### 4. degrees

- 描述：`degrees ( double precision ) → double precision`

- 函数功能：把弧度转为角度

- 源代码实现

  - **degrees**

    - `src\backend\utils\adt\float.c`

      - ```c++
        #define CHECKFLOATVAL do { if (isinf(val) && !(inf_is_valid)) ereport(ERROR, (errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE), errmsg("value out of range: overflow"))); if ((val) == 0.0 && !(zero_is_valid)) ereport(ERROR, (errcode(ERRCODE_NUMERIC_VALUE_OUT_OF_RANGE), errmsg("value out of range: underflow"))); } while(0)
        ```

    - `src\include\c.h`

      - ```c++
        #define pg_unreachable __assume(0)
        ```

    - `src\include\fmgr.h`

      - ```c++
        #define PG_FUNCTION_ARGS FunctionCallInfo fcinfo
        #define PG_GETARG_DATUM (fcinfo->arg[n])
        #define PG_GETARG_FLOAT8 DatumGetFloat8(PG_GETARG_DATUM(n))
        #define PG_RETURN_FLOAT8 return Float8GetDatum(x)
        ```

    - `src\include\postgres.h`

      - ```c++
        #define DatumGetFloat8 (* ((float8 *) DatumGetPointer(X)))
        #define DatumGetPointer ((Pointer) (X))
        ```

    - `src\backend\utils\fmgr\fmgr.c`

      - ```c++
        Datum
        Float8GetDatum(float8 X)
        {
        #ifdef USE_FLOAT8_BYVAL
        	union
        	{
        		float8		value;
        		int64		retval;
        	}			myunion;
        
        	myunion.value = X;
        	return SET_8_BYTES(myunion.retval);
        #else
        	float8	   *retval = (float8 *) palloc(sizeof(float8));
        
        	*retval = X;
        	return PointerGetDatum(retval);
        #endif
        }
        ```

    - `src\include\utils\elog.h`

      - ```c++
        #define ERROR 20
        #define PG_FUNCNAME_MACRO NULL
        #define TEXTDOMAIN NULL
        #define ereport ereport_domain(elevel, TEXTDOMAIN, rest)
        #define ereport_domain do { const int elevel_ = (elevel); if (errstart(elevel_, __FILE__, __LINE__, PG_FUNCNAME_MACRO, domain)) errfinish rest; if (elevel_ >= ERROR) pg_unreachable(); } while(0)
        ```

    - `src\bin\pgbench\pgbench.c`

      - ```c++
        #define M_PI 3.14159265358979323846
        ```
    
    - `src\backend\utils\adt\float.c`
    
      - ```c++
        Datum
        degrees(PG_FUNCTION_ARGS)
        {
        	float8		arg1 = PG_GETARG_FLOAT8(0);
        	float8		result;
    
        	result = arg1 * (180.0 / M_PI);
    
        	CHECKFLOATVAL(result, isinf(arg1), arg1 == 0);
        	PG_RETURN_FLOAT8(result);
        }
    ```

### 5. div

- 描述：`div ( y numeric, x numeric ) → numeric`

- 函数功能：计算 y/x

- 源代码实现

  - **numeric_div_trunc**

    - `src\include\c.h`

      - ```c++
        #define LONG_ALIGN_MASK (sizeof(long) - 1)
        #define MemSetAligned do { long *_start = (long *) (start); int _val = (val); Size _len = (len); if ((_len & LONG_ALIGN_MASK) == 0 && _val == 0 && _len <= MEMSET_LOOP_LIMIT && MEMSET_LOOP_LIMIT != 0) { long *_stop = (long *) ((char *) _start + _len); while (_start < _stop) *_start++ = 0; } else memset(_start, _val, _len); } while (0)
        #define false ((bool) 0)
        struct varlena
        {
        	char		vl_len_[4];		/* Do not touch this field directly! */
        	char		vl_dat[FLEXIBLE_ARRAY_MEMBER];	/* Data content is here */
        };
        ```

    - `src\include\fmgr.h`

      - ```c++
        #define PG_DETOAST_DATUM pg_detoast_datum((struct varlena *) DatumGetPointer(datum))
        #define PG_FUNCTION_ARGS FunctionCallInfo fcinfo
        #define PG_GETARG_DATUM (fcinfo->arg[n])
        ```

    - `src\backend\utils\fmgr\fmgr.c`

      - ```c++
        struct varlena *
        pg_detoast_datum(struct varlena * datum)
        {
        	if (VARATT_IS_EXTENDED(datum))
        		return heap_tuple_untoast_attr(datum);
        	else
        		return datum;
        }
        ```

    - `src\include\postgres.h`

      - ```c++
        #define DatumGetPointer ((Pointer) (X))
        #define PointerGetDatum ((Datum) (X))
        ```

    - `src\include\utils\numeric.h`

      - ```c++
        #define DatumGetNumeric ((Numeric) PG_DETOAST_DATUM(X))
        #define NumericGetDatum PointerGetDatum(X)
        #define PG_GETARG_NUMERIC DatumGetNumeric(PG_GETARG_DATUM(n))
        #define PG_RETURN_NUMERIC return NumericGetDatum(x)
        ```

    - `src\backend\utils\adt\numeric.c`

      - ```c++
        #define NUMERIC_FLAGBITS ((n)->choice.n_header & NUMERIC_SIGN_MASK)
        #define NUMERIC_IS_NAN (NUMERIC_FLAGBITS(n) == NUMERIC_NAN)
        #define NUMERIC_SIGN_MASK 0xC000
        static void
        div_var(NumericVar *var1, NumericVar *var2, NumericVar *result,
        		int rscale, bool round)
        {
        // 省略
        }
        static void
        free_var(NumericVar *var)
        {
        	digitbuf_free(var->buf);
        	var->buf = NULL;
        	var->digits = NULL;
        	var->sign = NUMERIC_NAN;
        }
        #define init_var MemSetAligned(v, 0, sizeof(NumericVar))
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
        static Numeric
        make_result(NumericVar *var)
        {
        // 省略
        }
        ```

    - `src\interfaces\ecpg\test\expected\sql-sqlda.c`

      - ```c++
        #define NUMERIC_NAN 0xC000
        ```

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
        
        	/*
        	 * Handle NaN
        	 */
        	if (NUMERIC_IS_NAN(num1) || NUMERIC_IS_NAN(num2))
        		PG_RETURN_NUMERIC(make_result(&const_nan));
        
        	/*
        	 * Unpack the arguments
        	 */
        	init_var_from_num(num1, &arg1);
        	init_var_from_num(num2, &arg2);
        
        	init_var(&result);
        
        	/*
        	 * Do the divide and return the result
        	 */
        	div_var(&arg1, &arg2, &result, 0, false);
        
        	res = make_result(&result);
        
        	free_var(&result);
        
        	PG_RETURN_NUMERIC(res);
        }
        ```

