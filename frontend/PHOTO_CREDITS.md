# Photography

All four photographs are real photographs published under the free [Unsplash licence](https://unsplash.com/license). They are illustrative food photographs, not photographs of experimentally tested EcoSwap recipes. No image generation is used.

| Dish | Photographer | Original photograph |
| --- | --- | --- |
| Pesto and sun-dried tomato pasta | Ella Olsson | https://unsplash.com/photos/n368kMQR1b0 |
| Paneer butter masala | Kalyani Akella | https://unsplash.com/photos/vgTntT8PmIM |
| Biryani and naan | LOLA AZIZADA | https://unsplash.com/photos/LxkWpGMEwlM |
| Salmon and quinoa bowl | Ella Olsson | https://unsplash.com/photos/KPDbRyFOTnE |

`npm run build` downloads 900 px and 1920 px WebP versions into `public/photos/` before bundling. Production serves those files from its own host. The development server uses the original image CDN until the production assets have been built. Credits are also linked on the How It Works page.
