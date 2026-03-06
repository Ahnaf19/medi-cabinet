# Medi-Cabinet Bot - User Guide

A complete guide for using the Medi-Cabinet Telegram bot in your family group chat.

## Getting Started

1. Add the bot to your family Telegram group
2. Send `/start` to see the welcome message
3. Start tracking your medicines!

The bot understands natural language in English. Just type how you'd normally talk about medicines.

---

## Adding Medicines

| What you type | What happens |
|---|---|
| `+Napa 10` | Adds 10 tablets of Napa |
| `+Capsule 5 caps` | Adds 5 capsules |
| `Bought Napa Extra 20 tablets` | Natural language add |
| `Got paracetamol, 12, expires Dec 2025` | With expiry date |
| `Added Napa 10 tablets in bedroom drawer` | With storage location |

If a medicine already exists, the quantity is increased.

## Using / Taking Medicines

| What you type | What happens |
|---|---|
| `-Napa 2` | Uses 2 tablets of Napa |
| `Used 2 Napa` | Same as above |
| `Took some paracetamol` | Uses 1 tablet (default) |

The bot warns you when stock gets low (below 3).

## Searching

| What you type | What happens |
|---|---|
| `?Napa` | Search for Napa |
| `Do we have Sergel?` | Natural question |
| `Check sergel` | Alternative search |

The bot uses fuzzy matching, so typos like "Nappa" still find "Napa".

## Listing All Medicines

| What you type | What happens |
|---|---|
| `?all` | List everything in the cabinet |
| `list medicines` | Same as above |
| `inventory` | Same as above |

---

## Routines & Reminders

Set up medicine reminders that the bot will send at the scheduled times.

### Adding a Routine

```
/routine add Napa at 08:00 daily before meal
/routine add Sergel at 8:00 AM and 8:00 PM daily after meal
```

You can also type naturally:
```
Take Napa at 08:00 daily before meal
Remind me Sergel every morning
```

**Supported options:**
- **Times**: `08:00`, `8:00 AM`, `2:30 PM`, or words like `morning`, `evening`, `afternoon`
- **Frequency**: `daily`, `weekly`, `every other day`
- **Meal relation**: `before meal`, `after meal`, `with meal`

### Managing Routines

| Command | Description |
|---|---|
| `/routine list` | View all your routines |
| `/routine pause 1` | Pause routine #1 |
| `/routine resume 1` | Resume routine #1 |
| `/routine delete 1` | Delete routine #1 |

### When a Reminder Fires

The bot sends a message with two buttons:
- **Taken** - Marks the dose as taken and deducts from inventory
- **Skip** - Marks it as skipped (no stock change)

If you don't respond, it's marked as missed.

---

## Drug Interaction Warnings

### Automatic Checks

When you add a new medicine, the bot automatically checks it against everything in your cabinet and warns about known interactions.

### Manual Check

```
/interactions Napa
```

Shows all known interactions for Napa with other medicines.

**Severity levels:**
- **Mild** - Minor interaction, usually safe
- **Moderate** - Use with caution
- **Severe** - Avoid combination if possible
- **Contraindicated** - Do not combine

---

## Cost Tracking

### Recording Costs

| Command | Description |
|---|---|
| `/cost Napa 50` | Record 50 BDT spent on Napa |
| `cost Napa 50tk` | Same as above |
| `Napa cost 100 taka` | Alternative format |

### Viewing Costs

```
/costs
```

Shows total spending and breakdown by medicine for the last 30 days.

---

## Photo Recognition

Send a photo of a medicine packet to the group chat. If LLM is configured, the bot will:

1. Analyze the photo using vision AI
2. Extract medicine name, quantity, and expiry
3. Ask you to confirm
4. Add it to your inventory

---

## Analytics

```
/analytics
```

Shows a comprehensive report including:
- Inventory summary (total medicines, low stock, expired)
- Activity patterns (most used medicines)
- Spending summary
- Adherence rate for routines
- Restock predictions (when medicines will run out)

---

## Admin Commands

These require your Telegram user ID to be in the `ADMIN_USER_IDS` config.

| Command | Description |
|---|---|
| `/delete Napa` | Permanently delete a medicine |
| `/stats` | Show usage statistics |

---

## Tips

- **Fuzzy matching**: Don't worry about exact spelling. "Nappa", "napa", "NAPA" all work.
- **Group isolation**: Each group chat has its own separate cabinet. Your family data stays private.
- **Expiry alerts**: The bot checks daily at 9 AM and warns about medicines expiring within 30 days.
- **Low stock**: Automatic warnings when any medicine drops below 3 units.
- **Natural language**: When in doubt, just type naturally. The bot will try to understand.
