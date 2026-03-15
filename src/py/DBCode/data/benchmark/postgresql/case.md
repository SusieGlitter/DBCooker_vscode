
/data/wei/code/postgres/src/backend/utils/adt/numeric.c

```
//PG_FUNCTION_INFO_V1(numeric_abs);
//Datum numeric_abs(PG_FUNCTION_ARGS)
//{
//    Numeric num = PG_GETARG_NUMERIC(0);
//    Numeric res;
//
//    if (NUMERIC_IS_NAN(num))
//        PG_RETURN_NUMERIC(make_result(&const_nan));
//
//    if (NUMERIC_SIGN(num) == NUMERIC_NEG)
//        res = make_result(&const_zero);
//    else
//        res = num;
//
//    PG_RETURN_NUMERIC(res);
//}


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


