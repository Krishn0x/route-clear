from decimal import Decimal, ROUND_HALF_EVEN

def to_paise(amount: Decimal) -> int:
    """
    Safely converts a Decimal INR amount to integer paise.
    Ensures that no sub-paise rounding occurs silently.
    """
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
        
    if amount < Decimal('0'):
        raise ValueError(f"Amount {amount} cannot be negative.")
        
    # Multiply by 100 for paise
    paise_decimal = amount * Decimal('100')
    
    # Check if there are fractional paise
    paise_int = paise_decimal.to_integral_value(ROUND_HALF_EVEN)
    if paise_decimal != paise_int:
        raise ValueError(f"Amount {amount} has sub-paise precision and cannot be safely converted.")
        
    return int(paise_int)
