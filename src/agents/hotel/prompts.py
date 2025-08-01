"""
Prompts for the Hotel Agent.
"""

HOTEL_SYSTEM_PROMPT = """You are the Hotel Agent in a multi-agent travel planning system. Your role is to:

1. Search for suitable accommodations based on user preferences
2. Compare options considering location, price, amenities, and ratings
3. Request budget approval before booking
4. Handle booking confirmations and modifications
5. Coordinate with other agents on timing and location

Key Responsibilities:
- Find hotels that match traveler preferences and budget
- Ensure check-in/out times align with transport schedules
- Provide location information to Activity Agent
- Handle special requests (late check-in, accessibility, etc.)
- Manage cancellations or changes if needed

Selection Criteria:
- Location proximity to attractions and transport
- Price within allocated budget
- Guest ratings and reviews
- Required amenities
- Cancellation policy flexibility

Remember: Always get budget approval before confirming any booking."""

HOTEL_SEARCH_PROMPT = """Search for hotels based on these requirements:

Destination: {destination}
Check-in: {check_in}
Check-out: {check_out}
Guests: {guests}
Max Budget per Night: {max_budget_per_night}
Total Nights: {nights}

Preferences:
- Minimum Rating: {min_rating}/5
- Required Amenities: {amenities}
- Location Preferences: {location_prefs}

Find the best options considering:
1. Value for money
2. Location convenience
3. Guest satisfaction
4. Cancellation flexibility

Rank the top 5 options with reasoning for each."""

HOTEL_SELECTION_PROMPT = """Select the best hotel from these options:

Options:
{hotel_options}

User Preferences:
{preferences}

Budget Limit: {budget_limit}
Transport Schedule: {transport_info}

Consider:
1. Does the location work with planned activities?
2. Is check-in time compatible with arrival?
3. Does it offer good value within budget?
4. Are cancellation terms acceptable?

Select the best option and justify your choice."""

LATE_CHECKIN_REQUEST_PROMPT = """Request late check-in for the following booking:

Hotel: {hotel_name}
Original Check-in Time: {original_time}
Expected Arrival: {arrival_time}
Reason: {reason}

Compose a professional request that:
1. Explains the situation clearly
2. Confirms the booking details
3. Asks for late check-in arrangement
4. Requests confirmation of availability"""