"""Author-defined scenarios; not scraped recipes or validated cooking outcomes."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
recipes=[]
def add(name,source,role,items,servings=4):
    rows=[]
    for item,grams in items.items():
        rows.append({'id':item,'grams':grams,'role':role if item==source else 'background'})
    recipes.append({'id':f'demo_{len(recipes)+1:02d}','name':name,'target':source,'servings':servings,
                    'ingredients':rows,'provenance':'Author-defined gram-based demonstration scenario; not a published or taste-tested recipe.',
                    'quantity_basis':'Use masses in the exact food states shown in ingredient_mapping.csv. Cooked grains/legumes are cooked weights; meats are raw weights.',
                    'instructions_note':'Ingredient-list adaptation only. Cooking methods and final texture need a separate kitchen pilot.'})

add('Beef and tomato pasta','beef','filling',dict(beef=400,pasta=600,tomato=400,onion=150,garlic=10,olive_oil=15,salt=3))
add('Beef and kidney bean chilli','beef','stew',dict(beef=400,kidney_beans=300,tomato=400,onion=150,olive_oil=15,pepper=2,salt=3))
add('Beef and potato pie filling','beef','filling',dict(beef=350,potato=600,carrot=150,onion=150,butter=25,milk=100,salt=3))
add('Beef rice bowl','beef','filling',dict(beef=300,rice=600,carrot=150,spinach=100,olive_oil=15,salt=3))
add('Lamb and lentil stew','lamb','stew',dict(lamb=400,lentils=300,tomato=300,onion=150,garlic=10,olive_oil=15,salt=3))
add('Lamb potato filling','lamb','filling',dict(lamb=350,potato=500,onion=150,carrot=100,olive_oil=15,salt=3))
add('Chicken tomato stew','chicken','stew',dict(chicken=400,tomato=400,onion=150,garlic=10,olive_oil=15,salt=3))
add('Chicken chickpea bowl','chicken','filling',dict(chicken=300,chickpeas=250,rice=500,spinach=100,olive_oil=15,salt=3))
add('Pork and bean stew','pork','stew',dict(pork=400,kidney_beans=300,tomato=300,onion=100,olive_oil=15,salt=3))
add('Pork pasta filling','pork','filling',dict(pork=350,pasta=600,tomato=400,onion=150,garlic=10,olive_oil=15,salt=3))
add('Butter-sauteed spinach','butter','saute',dict(butter=50,spinach=400,garlic=10,salt=2),2)
add('Butter-sauteed carrots','butter','saute',dict(butter=50,carrot=500,onion=100,salt=2),3)
add('Butter biscuit batter','butter','baking',dict(butter=100,flour=250,sugar=80,egg=100,milk=60,salt=2),6)
add('Butter cake batter','butter','baking',dict(butter=120,flour=220,sugar=120,egg=150,milk=100,salt=2),8)
add('Creamy spinach pasta','cream','sauce',dict(cream=200,pasta=600,spinach=250,onion=100,garlic=10,olive_oil=10,salt=3))
add('Creamy tomato soup','cream','sauce',dict(cream=200,tomato=600,onion=150,garlic=10,olive_oil=15,salt=3))
add('Creamy potato sauce','cream','sauce',dict(cream=200,potato=600,milk=100,garlic=10,salt=3))
add('Creamy lentil curry base','cream','sauce',dict(cream=150,lentils=500,tomato=250,onion=150,olive_oil=15,salt=3))
add('Milk rice pudding','milk','batter',dict(milk=600,rice=300,sugar=70),4)
add('Milk pancake batter','milk','batter',dict(milk=300,flour=200,egg=100,butter=20,sugar=20,salt=2),4)
add('Milk white sauce','milk','sauce',dict(milk=500,flour=40,butter=40,pepper=1,salt=2),4)
add('Cheddar potato topping','cheddar','topping',dict(cheddar=120,potato=600,milk=150,butter=20,salt=2))
add('Cheddar pasta bake topping','cheddar','topping',dict(cheddar=150,pasta=600,tomato=400,onion=100,olive_oil=15,salt=3))
add('Parmesan spinach pasta topping','parmesan','topping',dict(parmesan=100,pasta=600,spinach=200,olive_oil=20,garlic=10,salt=2))

if __name__=='__main__':
    (ROOT/'data/recipes.json').write_text(json.dumps(recipes,indent=2),encoding='utf-8')
    print(f'Wrote {len(recipes)} explicitly authored scenarios')
