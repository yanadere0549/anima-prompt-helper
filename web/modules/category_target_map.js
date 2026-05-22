/**
 * category_target_map.js — カテゴリとComposerフィールドの対応定義
 *
 * AnimaPromptComposer に残るタブと、各カテゴリのデフォルト挿入先を定義する。
 */

/**
 * Composer の入力フィールドに直接対応するタブ。
 * この4つだけが AnimaPromptComposer パネルに表示される。
 * @type {string[]}
 */
export const COMPOSER_ONLY_TABS = [];

/**
 * 各カテゴリのデフォルト挿入先（AnimaPromptComposer のフィールド名）。
 *
 * Preconditions:
 *   - すべての値は AnimaPromptComposer の widget name か "general" のいずれか。
 * @type {Object.<string, string>}
 */
export const CATEGORY_DEFAULT_TARGET = {
  quality: "quality",
  year: "year",
  rating: "rating",
  count: "count",
  hair_color: "general",
  hair_length: "general",
  hair_style: "general",
  eye_color: "general",
  expression: "general",
  pose: "general",
  composition: "general",
  clothing: "general",
  location: "general",
  lighting: "general",
  style: "general",
  effects: "general",
  artist: "artist",
  natural_language: "natural_language",
  accessory: "general",
  weapon: "general",
  food: "general",
  animal: "general",
  situation: "general",
  camera: "general",
  color_tone: "general",
  weather_atmos: "general",
  season: "general",
  architecture: "general",
  magic_fantasy: "general",
  accessory_floral: "general",
};

/**
 * AnimaTagPalette UI の「挿入先」dropdown に表示するフィールド候補。
 * @type {string[]}
 */
export const TARGET_FIELD_OPTIONS = [
  "general",
  "character",
  "series",
  "artist",
  "natural_language",
  "count",
  "year",
  "rating",
  "quality",
];
