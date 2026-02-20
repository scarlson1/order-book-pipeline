"""Data formatting utilities.

Provides formatting helpers for order book metrics and other dashboard data.
"""
from datetime import datetime
from typing import Optional, Union


def format_number(
    value: Optional[Union[int, float]],
    precision: int = 2,
    prefix: str = "",
    suffix: str = "",
    default: str = "—"
) -> str:
    """Format a number with optional prefix/suffix and precision.
    
    Args:
        value: The number to format
        precision: Number of decimal places
        prefix: String to prepend (e.g., '$')
        suffix: String to append (e.g., 'M', 'K')
        default: Value to return if input is None or NaN
        
    Returns:
        Formatted string representation
        
    Examples:
        >>> format_number(1234.567, precision=2)
        '1234.57'
        >>> format_number(50000.0, prefix='$')
        '$50000.00'
        >>> format_number(1500000, precision=1, suffix='M')
        '1.5M'
    """
    if value is None:
        return default
    
    try:
        num_value = float(value)
        if num_value != num_value:  # Check for NaN
            return default
    except (TypeError, ValueError):
        return default
    
    formatted = f"{num_value:,.{precision}f}"
    return f"{prefix}{formatted}{suffix}"


def format_price(
    price: Optional[float],
    precision: int = 2,
    currency: str = "",
    default: str = "—"
) -> str:
    """Format a price value with currency symbol.
    
    Args:
        price: The price to format
        precision: Number of decimal places
        currency: Currency symbol (e.g., '$', '₿')
        default: Value to return if input is None
        
    Returns:
        Formatted price string
        
    Examples:
        >>> format_price(50000.00)
        '$50,000.00'
        >>> format_price(0.00001234, precision=6)
        '0.000012'
    """
    if price is None:
        return default
    
    try:
        formatted = f"{float(price):,.{precision}f}"
        return f"{currency}{formatted}" if currency else formatted
    except (TypeError, ValueError):
        return default


def format_volume(
    volume: Optional[float],
    abbreviated: bool = False,
    default: str = "—"
) -> str:
    """Format a volume value, optionally abbreviating large numbers.
    
    Args:
        volume: The volume to format
        abbreviated: Whether to use K/M/B suffixes for large numbers
        default: Value to return if input is None
        
    Returns:
        Formatted volume string
        
    Examples:
        >>> format_volume(1500.5)
        '1,500.50'
        >>> format_volume(1500000, abbreviated=True)
        '1.50M'
    """
    if volume is None:
        return default
    
    try:
        vol = float(volume)
    except (TypeError, ValueError):
        return default
    
    if abbreviated:
        if vol >= 1_000_000_000:
            return f"{vol / 1_000_000_000:.2f}B"
        elif vol >= 1_000_000:
            return f"{vol / 1_000_000:.2f}M"
        elif vol >= 1_000:
            return f"{vol / 1_000:.2f}K"
    
    return f"{vol:,.2f}"


def format_percentage(
    value: Optional[float],
    precision: int = 2,
    include_sign: bool = False,
    default: str = "—"
) -> str:
    """Format a value as a percentage.
    
    Args:
        value: The decimal value (e.g., 0.65 for 65%)
        precision: Number of decimal places
        include_sign: Whether to show + sign for positive values
        default: Value to return if input is None
        
    Returns:
        Formatted percentage string
        
    Examples:
        >>> format_percentage(0.6543)
        '65.43%'
        >>> format_percentage(-0.15, include_sign=True)
        '-15.00%'
        >>> format_percentage(0.25, precision=0)
        '25%'
    """
    if value is None:
        return default
    
    try:
        pct = float(value) * 100
    except (TypeError, ValueError):
        return default
    
    formatted = f"{abs(pct):.{precision}f}"
    
    if include_sign:
        sign = "+" if pct > 0 else "-"
        return f"{sign}{formatted}%"
    
    return f"{formatted}%"


def format_bps(
    value: Optional[float],
    precision: int = 2,
    default: str = "—"
) -> str:
    """Format a basis point value.
    
    Args:
        value: The value in basis points
        precision: Number of decimal places
        default: Value to return if input is None
        
    Returns:
        Formatted bps string
        
    Examples:
        >>> format_bps(2.5)
        '2.50 bps'
        >>> format_bps(0.125, precision=3)
        '0.125 bps'
    """
    if value is None:
        return default
    
    try:
        formatted = f"{float(value):.{precision}f}"
        return f"{formatted} bps"
    except (TypeError, ValueError):
        return default


def format_datetime(
    value: Optional[datetime],
    format: str = "default",
    timezone: Optional[str] = None,
    default: str = "—"
) -> str:
    """Format a datetime value.
    
    Args:
        value: The datetime to format
        format: Format preset ('default', 'time', 'date', 'full', 'relative')
        timezone: Optional timezone name (e.g., 'UTC', 'America/New_York')
        default: Value to return if input is None
        
    Returns:
        Formatted datetime string
        
    Examples:
        >>> format_datetime(datetime(2024, 1, 15, 10, 30, 0))
        'Jan 15, 2024, 10:30 AM'
        >>> format_datetime(dt, format='time')
        '10:30:00'
        >>> format_datetime(dt, format='relative')
        '5 minutes ago'
    """
    if value is None:
        return default
    
    if not isinstance(value, datetime):
        return default
    
    # Format presets
    format_presets = {
        "default": "%b %d, %Y, %I:%M %p",
        "time": "%H:%M:%S",
        "time_short": "%H:%M",
        "date": "%Y-%m-%d",
        "date_short": "%b %d",
        "full": "%Y-%m-%d %H:%M:%S",
        "iso": "%Y-%m-%dT%H:%M:%S",
    }
    
    fmt = format_presets.get(format, format)
    
    try:
        result = value.strftime(fmt)
        
        # Add timezone if specified
        if timezone:
            result += f" {timezone}"
        
        return result
    except (ValueError, TypeError):
        return default


def format_imbalance(
    value: Optional[float],
    include_direction: bool = True,
    default: str = "—"
) -> str:
    """Format an imbalance ratio with direction indicator.
    
    Args:
        value: The imbalance ratio (-1 to 1)
        include_direction: Whether to show BUY/SELL indicator
        default: Value to return if input is None
        
    Returns:
        Formatted imbalance string
        
    Examples:
        >>> format_imbalance(0.65)
        '65% BUY'
        >>> format_imbalance(-0.3, include_direction=False)
        '30%'
    """
    if value is None:
        return default
    
    try:
        pct = abs(float(value)) * 100
    except (TypeError, ValueError):
        return default
    
    direction = ""
    if include_direction:
        if value > 0.05:
            direction = "BUY"
        elif value < -0.05:
            direction = "SELL"
        else:
            direction = "NEUTRAL"
        return f"{pct:.1f}% {direction}"
    
    return f"{pct:.1f}%"


def get_color_for_imbalance(
    value: Optional[float],
    theme: str = "default"
) -> str:
    """Get a color based on imbalance ratio for visual indicators.
    
    Args:
        value: The imbalance ratio (-1 to 1)
        theme: Color theme ('default', 'streamlit', 'green_red', 'blue_orange')
        
    Returns:
        Hex color code for the imbalance
        
    Color scheme:
        - Positive (> 0.05): Green/blue - buy pressure
        - Negative (< -0.05): Red/orange - sell pressure
        - Neutral (-0.05 to 0.05): Gray/yellow - balanced
        
    Examples:
        >>> get_color_for_imbalance(0.65)
        '#22C55E'  # Green
        >>> get_color_for_imbalance(-0.3)
        '#EF4444'  # Red
        >>> get_color_for_imbalance(0.0)
        '#6B7280'  # Gray
    """
    if value is None:
        return "#6B7280"  # Default gray
    
    themes = {
        "default": {
            "buy": "#22C55E",      # Green
            "sell": "#EF4444",     # Red
            "neutral": "#6B7280",  # Gray
        },
        "streamlit": {
            "buy": "#00CC96",      # Streamlit green
            "sell": "#EF553B",     # Streamlit red
            "neutral": "#636EFA",  # Streamlit blue
        },
        "green_red": {
            "buy": "#10B981",      # Emerald green
            "sell": "#DC2626",     # Red
            "neutral": "#F59E0B", # Amber
        },
        "blue_orange": {
            "buy": "#3B82F6",      # Blue
            "sell": "#F97316",     # Orange
            "neutral": "#8B5CF6",  # Purple
        },
    }
    
    colors = themes.get(theme, themes["default"])
    
    if value > 0.05:
        return colors["buy"]
    elif value < -0.05:
        return colors["sell"]
    else:
        return colors["neutral"]


def get_color_for_severity(severity: str) -> str:
    """Get a color based on alert severity level.
    
    Args:
        severity: Alert severity ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
        
    Returns:
        Hex color code for the severity level
        
    Examples:
        >>> get_color_for_severity('LOW')
        '#22C55E'
        >>> get_color_for_severity('CRITICAL')
        '#DC2626'
    """
    severity_colors = {
        "LOW": "#22C55E",       # Green
        "MEDIUM": "#F59E0B",    # Amber
        "HIGH": "#F97316",      # Orange
        "CRITICAL": "#DC2626",  # Red
    }
    
    return severity_colors.get(severity.upper(), "#6B7280")
