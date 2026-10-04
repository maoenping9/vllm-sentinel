* [Home](https://www.rainmeter.net/)
* [Documentation](https://docs.rainmeter.net/index.html)
* [Discover](https://rainmeter.net/discover)
* [Community](https://forum.rainmeter.net/)
#### [Manual](https://docs.rainmeter.net/manual)
---
#### Contents
* [Getting Started](https://docs.rainmeter.net/manual/getting-started/)
* [Installing Rainmeter](https://docs.rainmeter.net/manual/installing-rainmeter/)
* [User Interface](https://docs.rainmeter.net/manual/user-interface/)
* [Installing Skins](https://docs.rainmeter.net/manual/installing-skins/)
* [Arranging Skins](https://docs.rainmeter.net/manual/arranging-skins/)
* [Distributing Skins](https://docs.rainmeter.net/manual/distributing-skins/)
#### Reference
* [Settings](https://docs.rainmeter.net/manual/settings/)
* [Skins](https://docs.rainmeter.net/manual/skins/)
* [Meters](https://docs.rainmeter.net/manual/meters/)
  + [General Options](https://docs.rainmeter.net/manual/meters/general-options/)
  + [Bar](https://docs.rainmeter.net/manual/meters/bar/)
  + [Bitmap](https://docs.rainmeter.net/manual/meters/bitmap/)
  + [Button](https://docs.rainmeter.net/manual/meters/button/)
  + [Histogram](https://docs.rainmeter.net/manual/meters/histogram/)
  + [Image](https://docs.rainmeter.net/manual/meters/image/)
  + [Line](https://docs.rainmeter.net/manual/meters/line/)
  + [Rotator](https://docs.rainmeter.net/manual/meters/rotator/)
  + [Roundline](https://docs.rainmeter.net/manual/meters/roundline/)
  + [Shape](https://docs.rainmeter.net/manual/meters/shape/)
  + [String](https://docs.rainmeter.net/manual/meters/string/)
    - [Inline Options](https://docs.rainmeter.net/manual/meters/string/inline/)
* [Measures](https://docs.rainmeter.net/manual/measures/)
* [Plugins](https://docs.rainmeter.net/manual/plugins/)
* [Bangs](https://docs.rainmeter.net/manual/bangs/)
* [Formulas](https://docs.rainmeter.net/manual/formulas/)
* [Variables](https://docs.rainmeter.net/manual/variables/)
* [Groups](https://docs.rainmeter.net/manual/groups/)
* [Mouse Actions](https://docs.rainmeter.net/manual/mouse-actions/)
* [Lua Scripting](https://docs.rainmeter.net/manual/lua-scripting/)
#### More
* [Tips & Tricks](https://docs.rainmeter.net/tips/)
* [Snippets](https://docs.rainmeter.net/snippets/)
* [Developers](https://docs.rainmeter.net/developers/)
* [Version History](https://docs.rainmeter.net/history/)
# String meter
---
`Meter=String` displays text.
## Options
General meter options
:   All [general meter options](https://docs.rainmeter.net/manual/meters/general-options/) are valid.
`MeasureName`, `MeasureName2`, ..., `MeasureNameN`
:   Name(s) of the measure(s) bound to the meter. The meter will display the current value of the measure defined in `MeasureName`, with values for additional measures bound to the meter available using the `%N` syntax in the [Text](https://docs.rainmeter.net/manual/meters/string/#Text) option.
    The meter does not require a `MeasureNameN` option if the [Text](https://docs.rainmeter.net/manual/meters/string/#Text) option alone will be used to define the string to display.
`Text` Default: `%1`
:   Text to display. If `MeasureName` is specified, `Text` will default to the value of the measure.
    The values of the measure(s) specified with `MeasureName` can be used with the `%N` syntax as follows:
    |  |
    | --- |
    | ``` MeasureName=SomeMeasure MeasureName2=SomeMeasure2 Text=This is text containing %1 and %2. ; %1 and %2 will be replaced by the string values of SomeMeasure and ; SomeMeasure2, respectively. ``` |
    [Copy](javascript:void(0);)
    The `Text` option can take any combination of the following forms:
    * Display the value of a measure bound with `MeasureName`
    * Display the values of multiple measures bound with `MeasureNameN`, and formatted with the `%N` syntax.
    * Display static text defined in the option.
    * Display the current value of any [variables](https://docs.rainmeter.net/manual/variables/) or [section variables](https://docs.rainmeter.net/manual/variables/section-variables/). *Note that the meter must contain the [DynamicVariables](https://docs.rainmeter.net/manual/meters/general-options/#DynamicVariables) option to use the current value of variables or measures defined as a section variable.*
`Prefix`
:   Text displayed before `Text`.
    **Note:** It is preferable to put the entire string in `Text` instead of using this option.
`Postfix`
:   Text displayed after `Text`.
    **Note:** It is preferable to put the entire string in `Text` instead of using this option.
`FontFace` Default: `Arial`
:   Family name of the font to use for the text. The font must either be installed in Windows directly or be [loaded at runtime](https://docs.rainmeter.net/manual/skins/resources-folder/#Fonts).
    **See also:** [Fonts Guide](https://docs.rainmeter.net/tips/fonts-guide/).
`FontSize` Default: `10.0`
:   Size of the font in points. Whole, half, and fractional points are accepted. E.g. `FontSize=8.5`.
`FontColor` Default: `0,0,0,255`
:   [Color](https://docs.rainmeter.net/manual/skins/option-types/#Color) of the font.
`FontWeight`
:   The weight of the font in the range 1-999.
    The following are common values and their meanings. If the value is supported by the font family, it will be used. If not, the closest value that is supported by the font family will be used.

    **100** - Thin (Hairline)
    **200** - Extra Light (Ultra Light)
    **300** - Light
    **350** - Semi Light
    **400** - Regular (Normal)
    **500** - Medium
    **600** - Semi Bold (Demi Bold)
    **700** - Bold
    **800** - Extra Bold (Ultra Bold)
    **900** - Black (Heavy)
    **950** - Extra Black (Ultra Black)

    If the font does not support any additional weights, then 500 and below will use the font's normal weight, and 600 and above will simulate a bold effect.
`StringAlign` Default: `Left`
:   Horizontal and vertical alignment of the string within the meter. Valid values are:
    * `Left`, `Right`, `Center` (or `LeftTop`, `RightTop`, `CenterTop`)
    * `LeftCenter`, `RightCenter`, `CenterCenter`
    * `LeftBottom`, `RightBottom`, `CenterBottom`
    The string will be aligned using the values of the `X` and or `Y` settings as the anchor point. So to CenterCenter align a string within a meter with a width and height of 100, set `X=50`, `Y=50` and `StringAlign=CenterCenter`.

    **StringAlign=Left** (the default)
    The string starts at X, and is drawn from there out to the right.
    *The result is that the string **begins at X**, and ends where it ends based on the length of the string.*
    X ==========>
    **StringAlign=Center**
    The string starts at X, and is drawn 1/2 back to the left, and 1/2 out to the right.
    *The result is that the string is **centered on X**. It begins where it begins and ends where it ends based on the length of the string.*
    <=====X=====>
    **StringAlign=Right**
    The string starts at X, and is drawn from there back to the left.
    *The result is that the string **ends at X**, and begins where it begins based on the length of the string.*
    <==========X
    The only important thing to remember to use StringAlign is that it is **always** based on the value of X or Y. The String meter with StringAlign is the one case where X or Y doesn't really mean "starts at", but rather means "is anchored at".
`StringStyle` Default: `Normal`
:   Style of the string. Valid values are `Normal`, `Bold`, `Italic`, and `BoldItalic`.
    **Note:** This option is for the most part deprecated and replaced by the far more powerful functionality in the [FontWeight](https://docs.rainmeter.net/manual/meters/string/#FontWeight) option above. It should only be used in new skins to obtain the *Italic* effect, and should not be used to control the weight attributes.
`StringCase` Default: `None`
:   Converts the string to a case. Valid values are `None`, `Upper`, `Lower`, and `Proper`.
`StringEffect` Default: `None`
:   Effect applied to a string. Valid values are `None`, `Shadow`, and `Border`.
    `Shadow` makes a background copy of the string, offset 1px "right" and 1px "down", in the color defined in `FontEffectColor`.
    `Border` makes a background copy of the string, 2px "larger", and offset 1px "left" and 1px "up", in the color defined in `FontEffectColor`.
    The size of the font used in the string has no effect on the fixed 1px size of the `Shadow` or `Border` effect.
    Due to how these effects are created, transparent colors on the string may have undesirable results.
`FontEffectColor` Default: `0,0,0,255`
:   [Color](https://docs.rainmeter.net/manual/skins/option-types/#Color) of the StringEffect.
`ClipString` Default: `0`
:   Controls how strings are truncated (clipped) or wrapped to fit in or expand the containing meter. Valid values are:
    * `0`: Disabled. The string will not be clipped or wrapped. (default)
    * `1`: Enabled. The string will be clipped with an added ellipsis `...` when it exceeds the specified `W` ([width](https://docs.rainmeter.net/manual/meters/general-options/#WH)) option on the meter. If the `H` ([height](https://docs.rainmeter.net/manual/meters/general-options/#WH)) option is large enough to allow multiple lines, the text is wrapped until the value of `H` is reached, then clipped.
    * `2`: Auto. The string will be clipped or wrapped based on the value of `W` and/or `H`. If the width or height are not specified, the meter itself will change size to accommodate the string. This setting works in conjunction with the [ClipStringW](https://docs.rainmeter.net/manual/meters/string/#ClipStringW) and [ClipStringH](https://docs.rainmeter.net/manual/meters/string/#ClipStringH) options below, to set a "maximum" size that the meter should expand to accommodate the string before clipping.
    **Notes:** The changing size of meters when `ClipString=2` can cause truncation issues with the overall window size of the skin, unless [DynamicWindowSize=1](https://docs.rainmeter.net/manual/skins/rainmeter-section/#DynamicWindowSize) is set in the [Rainmeter] section of the skin.
    `ClipString=2` will always wrap on word boundaries (spaces or tabs). Any single word that is longer than the defined or maximum width will clip that line, rather than breaking the word in two.
    When `ClipString=2` is used with bound measures that have an initial value of "", (WebParser and QuotePlugin for example) [DynamicVariables=1](https://docs.rainmeter.net/manual/meters/general-options/#DynamicVariables) must be set on the meter.
`ClipStringW`
:   Sets a maximum width that the meter will expand to accommodate the string when `ClipString=2`. This setting is ignored if the `W` option is set.
`ClipStringH`
:   Sets a maximum height that the meter will expand to accommodate the string when `ClipString=2`. This setting is ignored if the `H` option is set.
`TrailingSpaces` Default: `0`
:   When this option is set to `1`, any `Text` option that is enclosed in "quotes" will display leading and trailing spaces on the string.
    Example: `Text="        This has leading and trailing spaces        "`
`Angle` Default: `0.0`
:   Defines the angle of the text in radians.
    **Note:** The size and position of the text are always calculated as if the text is horizontal. This also means that the click-able field used for [Mouse Actions](https://docs.rainmeter.net/manual/mouse-actions/) does not change. It remains where the text would be with no Angle.
    More information about using Angle can be found at [Working with Angle on a String Meter](https://forum.rainmeter.net/viewtopic.php?p=104103).
`Percentual` Default: `0`
:   If set to `1`, the value of bound measures are converted to a [percentage](https://docs.rainmeter.net/manual/measures/#Percentage). This is useful if a measure does not return a percentage value, but either automatically defines a valid "range" of values (e.g. [FreeDiskSpace](https://docs.rainmeter.net/manual/measures/freediskspace/)) or when the [MinValue](https://docs.rainmeter.net/manual/measures/general-options/#MinValue) and/or [MaxValue](https://docs.rainmeter.net/manual/measures/general-options/#MaxValue) options are manually set on the measure.
`NumOfDecimals` Default: `0`
:   Number of decimals to display with numerical measure values.
`Scale` Default: `1`
:   Scaling factor used for the measure values. The measure value is divided by the specified value. If the specified value has a decimal point (e.g. `1000.0`), the result will also display decimals.
    **Note:** If `AutoScale` is enabled, this option is ignored.
`AutoScale` Default: `0`
:   Automatically scales the measure values. The scaled result is appended with k, M, G, etc. as appropriate. Valid values are:
    * `0`: Disabled.
    * `1`: Scales by 1024.
    * `1k`: Scales by 1024 with kilo as the lowest unit.
    * `2`: Scales by 1000.
    * `2k`: Scales by 1000 with kilo as the lowest unit.
    By default the value will be displayed with one decimal point of precision. Use [NumOfDecimals](https://docs.rainmeter.net/manual/meters/string/#NumOfDecimals) to control this.
    **Note:** The value returned by AutoScale adds a space between the scaled number and the scale unit abbreviation. To remove this space simply add `Substitute=" ":""` to the Measure that the AutoScale is being applied to.
## Note:
Using the [SolidColor](https://docs.rainmeter.net/manual/meters/general-options/#SolidColor) option, with a value of `SolidColor=0,0,0,1`, will give a string meter a solid but virtually transparent background. This can make executing [mouse actions](https://docs.rainmeter.net/manual/mouse-actions/) on the text easier and more reliable.
## Example
|  |
| --- |
| ``` [Rainmeter] Update=1000 AccurateText=1 DynamicWindowSize=1  [Metadata] Name=ExampleMeterString Author=The Rainmeter Team Information=Example of the String meter License=Creative Commons Attribution-Non-Commercial-Share Alike 3.0 Version=1.0  [MeasureDate] Measure=Time Format=%A, %b %#d, %Y  [MeterDate] Meter=String MeasureName=MeasureDate X=0 Y=0 FontColor=255,255,255,255 FontFace=Segoe UI FontSize=17 StringEffect=Shadow FontEffectColor=0,0,0,255 AntiAlias=1 Text=Today is: %1  [MeterText1] Meter=String X=0 Y=0R FontColor=197,239,252,255 FontSize=12 AntiAlias=1 Text=Relative to bottom of previous meter  [MeterText2] Meter=String X=300 Y=10R W=300 H=20 StringAlign=Right FontColor=255,255,255,255 FontSize=14 FontWeight=400 StringStyle=Italic AntiAlias=1 Text=Right justified italic text  [MeterText3] Meter=String X=150 Y=5R W=300 H=20 StringAlign=Center FontColor=252,245,197,255 FontSize=14 FontWeight=700 AntiAlias=1 Text=Centered bold text  [MeterText4] Meter=String X=0 Y=10R W=200 H=50 FontColor=197,252,223,255 FontSize=14 FontWeight=700 ClipString=1 AntiAlias=1 Text="This text will wrap due to ClipString=1" ``` |
[Copy](javascript:void(0);)[Download](https://docs.rainmeter.net/manual/examples/ExampleMeterString.rmskin)
An example skin showing various string options.
© 2026 Rainmeter Team
Dark theme
