import time
import requests 
from mine import app 
import pyrogram

pyro = pyrogram.__version__

challenger_data = {}

fallback_words = {
    4: ['play', 'word', 'game', 'chat', 'abet', 'bark', 'card', 'dart', 'earn', 'fade', 
 'gaze', 'hail', 'idea', 'jade', 'keen', 'lamb', 'mild', 'nest', 'oath', 'pace', 
 'quiz', 'rage', 'salt', 'tame', 'undo', 'vast', 'wade', 'yarn', 'zeal', 'afar', 
 'bend', 'clad', 'dine', 'emit', 'flee', 'hush', 'inch', 'jolt', 'knot', 'lure', 
 'moth', 'numb', 'omit', 'pond', 'quip', 'rift', 'sage', 'tide', 'apex', 'bane', 
 'cove', 'dusk', 'fawn', 'gale', 'hymn', 'isle', 'jest', 'kale', 'loom', 'mire', 
 'nook', 'ogle', 'pith', 'quay', 'rove', 'sear', 'trek', 'veto', 'wane', 'yoke', 
 'zest', 'alms', 'brim', 'cusp', 'dolt', 'fret', 'grit', 'hewn', 'idle', 'knob', 
 'limp', 'mend', 'nape', 'oust', 'pry', 'raze', 'sift', 'taut', 'vial', 'writ', 
 'zany', 'akin', 'blot', 'chop', 'damp', 'envy', 'flap', 'gush', 'haze', 'inky', 
 'lisp', 'moat', 'opal', 'pact', 'rant', 'scum', 'twit', 'urge', 'vain', 'whiz', 
 'yelp', 'zinc', 'arch', 'blur', 'crux', 'deft', 'fizz', 'glow', 'harp', 'itch', 
 'judo', 'keto', 'lame', 'muse', 'nude', 'oxen', 'peck', 'skim', 'toil', 'vice', 
 'wiry', 'yolk', 'zaps', 'axis', 'boil', 'curl', 'dare', 'etch', 'flaw', 'glum', 
 'honk', 'irks', 'jamb', 'keel', 'lurk', 'mock', 'nigh', 'ooze', 'poke', 'roar', 
 'spit', 'tarp', 'unto', 'wage'],

    5: [
    "guess", "brain", "smart", "think", "apple", "bread", "charm", "doubt", "eager", "flame",
    "globe", "heart", "image", "joker", "knock", "lemon", "mango", "nerve", "ocean", "peace",
    "queen", "rider", "storm", "table", "urban", "vivid", "wrist", "xenon", "yield", "zebra",
    "angel", "blaze", "craft", "dream", "elite", "fancy", "grape", "haste", "ivory", "jolly",
    "kneel", "lunar", "march", "novel", "onion", "power", "quiet", "raven", "scope", "trust",
    "amber", "beach", "candy", "daisy", "eagle", "frost", "glide", "inlet", "jumpy", "koala",
    "latch", "mercy", "noble", "orbit", "plush", "quirk", "rusty", "spine", "trick", "unity",
    "vowel", "whale", "youth", "zesty", "adobe", "bloom", "cabin", "dwell", "exile",
    "fiery", "gloom", "hover", "ideal", "knead", "lyric", "mirth", "nudge", "olive", "piano",
    "quilt", "risky", "shiny", "torch", "udder", "vigor", "woven", "asset", "brisk",
    "chill", "dealt", "ethos", "flock", "grasp", "input", "latch", "mirth", "noble",
    "optic", "plume", "quest", "risky", "scout", "tulip", "unite", "verge", "whisk", "xerox",
    "yacht", "zoned", "amaze", "bison", "crisp", "drape", "eject", "flora", "glint", "imply",
    "jumbo", "knoll", "meaty", "nifty", "onset", "pouch", "roost", "swift", "tempo",
    "undue", "vixen", "waist", "brace", "choke", "deter", "fraud", "gleam",
    "hinge", "icily", "knees", "leash", "mince", "nerdy", "ounce", "proud", "rover",
    "slant", "ulcer", "wager", "yells", "alarm", "blunt", "creek", "drown", "exert",
    "flint", "gravy", "hasty", "irony", "joint", "knack", "lymph", "mount", "overt",
    "quash", "ranch", "spore", "tacit", "uncut", "wrath", "yeast"
],

    6: [
    "breeze", "baffle", "brogue", "chintz", "crisps", "dactyl", "decoct", "effigy", "elicit",
    "enigma", "engulf", "fickle", "fjords", "frugal", "hassle",
    "jabber", "jigsaw", "jungle", "lagoon", "lummox", "mumble", "nuzzle", "obtuse",
    "ocelot", "quasar", "squawk", "strive", "thwack", "vexing",
    "zephyr", "abduct", "banter", "candid", "debate", "fabric",
    "galaxy", "ignite", "jargon", "kernel", "lament", "mantle", "nectar", "pardon", "quaint",
    "ransom", "safari", "tandem", "vacuum", "wander", "zealot", "abound", "beacon", "cajole",
    "dainty", "fathom", "glisten", "hurdle", "influx", "jovial", "lucent", "mellow", "nurture",
    "oblige", "plaque", "quiver", "reside", "seldom", "thrive", "unveil", "verbal", "whimsy",
    "abacus", "badger", "cactus", "dagger", "falcon", "gadget", "hazard", "insect", "jacket",
    "ladder", "magnet", "napkin", "pencil", "quartz", "rocket", "saddle", "tunnel", "violet",
    "walnut", "anchor", "candle", "donkey", "engine", "goblin", "helmet", "island", "monkey",
    "oyster", "parrot", "admire", "bakery", "ballot", "ballet", "barren", "beetle", "blazer",
    "bounce", "brandy", "bridge", "bronze", "bundle", "butter", "canyon", "castle", "celery",
    "cheese", "chorus", "clergy", "coffee", "cotton", "couple", "coyote", "cradle", "cruise",
    "custom", "damage", "debate", "defeat", "depart", "desert", "divide", "donate", "dragon",
    "drawer", "elegant", "embark", "emerge", "empire", "enrich", "escape", "exceed", "expose",
    "fabric", "famous", "farmer", "fathom", "feline", "fossil"
],

    7: [
    "amazing", "thought", "journey", "fantasy", "balance", "captain", "densely", "embrace", "freight", 
    "gallery", "harvest", "imagine", "justice", "kingdom", "lantern", "machine", "natural", "opinion", 
    "passion", "quality", "recover", "shelter", "theatre", "uniform", "venture", "whisper", "zealous", 
    "absolve", "bargain", "clarify", "delight", "endless", "fragile", "genuine", "horizon", "insight", 
    "jackpot", "kinetic", "magnify", "nurture", "outcome", "perform", "quieter", "respect", 
    "sincere", "trouble", "upright", "vibrant", "welcome", "bizarre", "cherish", "default", "echelon", 
    "fixture", "glamour", "hammock", "impulse", "javelin", "knuckle", "lullaby", "mammoth", "nostril", 
    "observe", "paddock", "radiant", "scratch", "tarnish", "vagrant", "waffles", "zippers", 
    "attract", "boycott", "combine", "dominate", "earnest", "fortune", "garland", "habitat", "iterate", 
    "kindred", "lavish", "migrate", "nomadic", "obvious", "private", "rapture", "senator", "torment", 
    "usually", "violent", "waylaid", "zealots", "acutely", "arsenal", "benefit", "calming", "destiny", 
    "elastic", "fabulous", "gravity", "hazards", "imitate", "joining", "keynote", "lengths", "majesty", 
    "musical", "obliged", "patient", "queries", "radical", "scenery", "therapy", "typical", "urbane", 
    "vantage", "warding", "zeolite", "advisor", "caramel", "dazzles", "effaced", "fumbles", 
    "glazier", "haughty", "implied", "kashmir", "looming", "mascots", "nouveau", "ostrich", "precise", 
    "quizzed", "retinal", "terrier", "ulterior", "varying", "warrant", "abiding", "affable", 
    "banquet", "bedding", "besiege", "bravado", "breeder", "brittle", "broiler", "calypso", "carbine", 
    "chaotic", "chronic", "cloning", "complex", "contend", "cordial", "cowhand", "cramped", "cubical", 
    "cunning", "cupcake", "cyclone", "dancing", "daytime", "deceive", "defiant", "demonic", "deposit", 
    "despair", "distant", "ditches", "doctors", "dodging", "dreamer", "dugouts", "dynamic", "eagerly", 
    "earshot", "ecstasy", "elegant", "elevate", "eloping"
]

}


print(f"PYRGOGRAM VERSION :- {pyro}")
print("FALLBACK WORDS LOADED✅")
print("CHALLENGER DATA LOADED✅")
