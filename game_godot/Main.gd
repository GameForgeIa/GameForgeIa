extends Node3D

# ⚠️ Remplace par l'URL de ton backend une fois déployé sur Render
const BACKEND_URL := "https://forgegameia-backend.onrender.com"/latest-level

const TILE_SIZE := 2.0

const TILE_COLORS := {
	"grass": Color(0.30, 0.55, 0.25),
	"dirt": Color(0.45, 0.32, 0.20),
	"water": Color(0.20, 0.40, 0.75),
	"wall": Color(0.35, 0.35, 0.38),
	"sand": Color(0.80, 0.72, 0.45),
}

const UNIT_COLORS := {
	"player": Color(0.25, 0.55, 0.95),
	"enemy": Color(0.90, 0.25, 0.25),
}

const HIGHLIGHT_MOVE := Color(0.3, 0.9, 0.4, 0.55)
const HIGHLIGHT_ATTACK := Color(0.95, 0.25, 0.25, 0.55)

@onready var http_request: HTTPRequest = $HTTPRequest
@onready var status_label: Label = $UI/StatusLabel
@onready var reload_button: Button = $UI/ReloadButton
@onready var turn_label: Label = $UI/TurnLabel
@onready var message_label: Label = $UI/MessageLabel
@onready var end_turn_button: Button = $UI/EndTurnButton
@onready var camera: Camera3D = $Camera3D

var level_root: Node3D
var tiles := {}      # "x_y" -> {height, type, walkable}
var units := []       # array de dictionnaires unit data (voir _add_unit)
var grid_width := 0
var grid_height := 0
var objective_text := ""

var turn := "player"  # "player" ou "enemy"
var selected_unit = null
var reachable := {}   # "x_y" -> cout de déplacement
var highlight_nodes := []
var game_over := false


func _ready() -> void:
	reload_button.pressed.connect(_fetch_level)
	end_turn_button.pressed.connect(_end_player_turn)
	http_request.request_completed.connect(_on_level_received)
	_fetch_level()


func _fetch_level() -> void:
	status_label.text = "Chargement du niveau..."
	var err := http_request.request(BACKEND_URL)
	if err != OK:
		status_label.text = "Erreur de requête (%s)" % err


func _on_level_received(_result, response_code, _headers, body: PackedByteArray) -> void:
	if response_code != 200:
		status_label.text = "Aucun niveau disponible (code %s). Crée-en un dans ForgeGameIA." % response_code
		return

	var json := JSON.new()
	var parse_err := json.parse(body.get_string_from_utf8())
	if parse_err != OK:
		status_label.text = "Réponse du serveur invalide."
		return

	var data: Dictionary = json.get_data()
	_build_level(data)
	status_label.text = "Niveau : %s" % data.get("name", "?")
	objective_text = data.get("objective", "Vaincre tous les ennemis.")
	message_label.text = "Objectif : " + objective_text


# ---------------------------------------------------------------------
# Construction du niveau
# ---------------------------------------------------------------------

func _build_level(data: Dictionary) -> void:
	if level_root:
		level_root.queue_free()
	level_root = Node3D.new()
	add_child(level_root)

	tiles.clear()
	units.clear()
	highlight_nodes.clear()
	game_over = false
	turn = "player"
	selected_unit = null
	reachable.clear()
	_update_turn_label()

	grid_width = data.get("grid_width", 8)
	grid_height = data.get("grid_height", 8)

	for tile in data.get("tiles", []):
		var key := _key(tile.get("x", 0), tile.get("y", 0))
		tiles[key] = {
			"height": max(tile.get("height", 0), 0.2),
			"type": tile.get("type", "grass"),
			"walkable": tile.get("type", "grass") != "wall",
		}
		_add_tile_visual(tile)

	for unit_data in data.get("units", []):
		_add_unit(unit_data)


func _key(x: int, y: int) -> String:
	return "%d_%d" % [x, y]


func _add_tile_visual(tile: Dictionary) -> void:
	var x: float = tile.get("x", 0)
	var y: float = tile.get("y", 0)
	var height: float = max(tile.get("height", 0), 0.2)
	var type: String = tile.get("type", "grass")

	var box := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = Vector3(TILE_SIZE * 0.95, height, TILE_SIZE * 0.95)
	box.mesh = mesh

	var material := StandardMaterial3D.new()
	material.albedo_color = TILE_COLORS.get(type, Color(0.5, 0.5, 0.5))
	box.material_override = material
	box.position = Vector3(x * TILE_SIZE, height / 2.0, y * TILE_SIZE)

	# Corps statique pour la détection tactile (clic/tap sur la tuile)
	var body := StaticBody3D.new()
	body.set_meta("grid_x", int(x))
	body.set_meta("grid_y", int(y))
	body.set_meta("kind", "tile")
	var shape := CollisionShape3D.new()
	var box_shape := BoxShape3D.new()
	box_shape.size = mesh.size
	shape.shape = box_shape
	body.add_child(shape)
	box.add_child(body)

	level_root.add_child(box)


func _add_unit(unit_data: Dictionary) -> void:
	var x: int = unit_data.get("x", 0)
	var y: int = unit_data.get("y", 0)
	var team: String = unit_data.get("team", "player")

	var capsule := MeshInstance3D.new()
	var mesh := CapsuleMesh.new()
	mesh.radius = 0.4
	mesh.height = 1.4
	capsule.mesh = mesh

	var material := StandardMaterial3D.new()
	material.albedo_color = UNIT_COLORS.get(team, Color.WHITE)
	capsule.material_override = material

	var body := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var capsule_shape := CapsuleShape3D.new()
	capsule_shape.radius = 0.45
	capsule_shape.height = 1.4
	shape.shape = capsule_shape
	body.add_child(shape)
	capsule.add_child(body)

	var hp_label := Label3D.new()
	hp_label.position = Vector3(0, 1.3, 0)
	hp_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	hp_label.font_size = 48
	capsule.add_child(hp_label)

	level_root.add_child(capsule)

	var unit := {
		"x": x, "y": y, "team": team,
		"type": unit_data.get("type", "unit"),
		"hp": unit_data.get("hp", 15),
		"max_hp": unit_data.get("hp", 15),
		"atk": unit_data.get("atk", 4),
		"move": unit_data.get("move", 4),
		"node": capsule,
		"body": body,
		"hp_label": hp_label,
		"acted": false,
	}
	body.set_meta("unit_ref", unit)
	units.append(unit)
	_update_unit_visual(unit)
	_update_unit_position(unit)


func _update_unit_position(unit: Dictionary) -> void:
	var height := tiles.get(_key(unit.x, unit.y), {}).get("height", 0.2)
	unit.node.position = Vector3(unit.x * TILE_SIZE, height + 0.9, unit.y * TILE_SIZE)


func _update_unit_visual(unit: Dictionary) -> void:
	unit.hp_label.text = "%s\n%d/%d" % [unit.type, unit.hp, unit.max_hp]
	var mat: StandardMaterial3D = unit.node.material_override
	mat.albedo_color.a = 1.0 if unit.hp > 0 else 0.15


# ---------------------------------------------------------------------
# Entrée tactile : sélection / déplacement / attaque
# ---------------------------------------------------------------------

func _unhandled_input(event: InputEvent) -> void:
	if game_over or turn != "player":
		return
	var pressed_pos: Vector2 = Vector2.ZERO
	var is_tap := false
	if event is InputEventScreenTouch and event.pressed:
		pressed_pos = event.position
		is_tap = true
	elif event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		pressed_pos = event.position
		is_tap = true
	if not is_tap:
		return

	var from := camera.project_ray_origin(pressed_pos)
	var dir := camera.project_ray_normal(pressed_pos)
	var space_state := get_world_3d().direct_space_state
	var query := PhysicsRayQueryParameters3D.create(from, from + dir * 100.0)
	var result := space_state.intersect_ray(query)
	if result.is_empty():
		return

	var collider = result["collider"]
	if collider.has_meta("unit_ref"):
		_on_unit_tapped(collider.get_meta("unit_ref"))
	elif collider.has_meta("grid_x"):
		_on_tile_tapped(collider.get_meta("grid_x"), collider.get_meta("grid_y"))


func _on_unit_tapped(unit: Dictionary) -> void:
	if unit.hp <= 0:
		return
	if unit.team == "player" and not unit.acted:
		selected_unit = unit
		reachable = _compute_reachable(unit)
		_refresh_highlights()
		message_label.text = "%s sélectionné. Touche une case verte pour bouger, une case rouge pour attaquer." % unit.type
	elif unit.team == "enemy" and selected_unit != null:
		_try_attack(selected_unit, unit)


func _on_tile_tapped(x: int, y: int) -> void:
	if selected_unit == null:
		return
	var key := _key(x, y)
	if reachable.has(key) and _unit_at(x, y) == null:
		selected_unit.x = x
		selected_unit.y = y
		_update_unit_position(selected_unit)
		selected_unit.acted = true
		_clear_highlights()
		message_label.text = "%s s'est déplacé." % selected_unit.type
		selected_unit = null
		reachable.clear()


func _try_attack(attacker: Dictionary, target: Dictionary) -> void:
	var dist: int = abs(attacker.x - target.x) + abs(attacker.y - target.y)
	if dist > 1:
		message_label.text = "Cible trop loin pour attaquer."
		return
	if attacker.acted:
		message_label.text = "Cette unité a déjà agi ce tour."
		return
	var damage: int = max(1, attacker.atk - 2)
	target.hp = max(0, target.hp - damage)
	_update_unit_visual(target)
	attacker.acted = true
	message_label.text = "%s attaque %s (-%d PV)." % [attacker.type, target.type, damage]
	_clear_highlights()
	selected_unit = null
	reachable.clear()
	_check_game_over()


# ---------------------------------------------------------------------
# Déplacement : recherche des cases atteignables (BFS)
# ---------------------------------------------------------------------

func _compute_reachable(unit: Dictionary) -> Dictionary:
	var result := {}
	var frontier := [[unit.x, unit.y, 0]]
	var visited := {_key(unit.x, unit.y): 0}
	while frontier.size() > 0:
		var current = frontier.pop_front()
		var cx: int = current[0]
		var cy: int = current[1]
		var cost: int = current[2]
		for delta in [[1, 0], [-1, 0], [0, 1], [0, -1]]:
			var nx: int = cx + delta[0]
			var ny: int = cy + delta[1]
			var nkey := _key(nx, ny)
			var tile = tiles.get(nkey)
			if tile == null or not tile.walkable:
				continue
			var next_cost: int = cost + 1
			if next_cost > unit.move:
				continue
			if visited.has(nkey) and visited[nkey] <= next_cost:
				continue
			if _unit_at(nx, ny) != null:
				continue
			visited[nkey] = next_cost
			result[nkey] = next_cost
			frontier.append([nx, ny, next_cost])
	return result


func _unit_at(x: int, y: int):
	for u in units:
		if u.hp > 0 and u.x == x and u.y == y:
			return u
	return null


func _refresh_highlights() -> void:
	_clear_highlights()
	for key in reachable.keys():
		var parts := key.split("_")
		var x := int(parts[0])
		var y := int(parts[1])
		var height = tiles[key].height
		var marker := MeshInstance3D.new()
		var mesh := BoxMesh.new()
		mesh.size = Vector3(TILE_SIZE * 0.8, 0.05, TILE_SIZE * 0.8)
		marker.mesh = mesh
		var mat := StandardMaterial3D.new()
		mat.albedo_color = HIGHLIGHT_MOVE
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		marker.material_override = mat
		marker.position = Vector3(x * TILE_SIZE, height + 0.05, y * TILE_SIZE)
		level_root.add_child(marker)
		highlight_nodes.append(marker)


func _clear_highlights() -> void:
	for n in highlight_nodes:
		if is_instance_valid(n):
			n.queue_free()
	highlight_nodes.clear()


# ---------------------------------------------------------------------
# Tours
# ---------------------------------------------------------------------

func _update_turn_label() -> void:
	turn_label.text = "Tour : %s" % ("Joueur" if turn == "player" else "Ennemis")


func _end_player_turn() -> void:
	if game_over or turn != "player":
		return
	selected_unit = null
	reachable.clear()
	_clear_highlights()
	turn = "enemy"
	_update_turn_label()
	message_label.text = "Tour des ennemis..."
	for u in units:
		u.acted = false
	await get_tree().create_timer(0.6).timeout
	_run_enemy_turn()


func _run_enemy_turn() -> void:
	for enemy in units:
		if game_over:
			return
		if enemy.team != "enemy" or enemy.hp <= 0:
			continue
		var target = _nearest_player_unit(enemy)
		if target == null:
			continue
		# Se déplacer vers la cible si pas déjà adjacent
		var dist: int = abs(enemy.x - target.x) + abs(enemy.y - target.y)
		if dist > 1:
			var reach: Dictionary = _compute_reachable(enemy)
			var best_key = null
			var best_dist := 9999
			for key in reach.keys():
				var parts := key.split("_")
				var x := int(parts[0])
				var y := int(parts[1])
				var d: int = abs(x - target.x) + abs(y - target.y)
				if d < best_dist:
					best_dist = d
					best_key = key
			if best_key != null:
				var parts2 := best_key.split("_")
				enemy.x = int(parts2[0])
				enemy.y = int(parts2[1])
				_update_unit_position(enemy)
				await get_tree().create_timer(0.3).timeout
			dist = abs(enemy.x - target.x) + abs(enemy.y - target.y)
		if dist <= 1:
			var damage: int = max(1, enemy.atk - 2)
			target.hp = max(0, target.hp - damage)
			_update_unit_visual(target)
			message_label.text = "%s attaque %s (-%d PV)." % [enemy.type, target.type, damage]
			_check_game_over()
			await get_tree().create_timer(0.4).timeout
			if game_over:
				return

	turn = "player"
	for u in units:
		u.acted = false
	_update_turn_label()
	message_label.text = "À toi de jouer."


func _nearest_player_unit(from_unit: Dictionary):
	var best = null
	var best_dist := 9999
	for u in units:
		if u.team == "player" and u.hp > 0:
			var d: int = abs(u.x - from_unit.x) + abs(u.y - from_unit.y)
			if d < best_dist:
				best_dist = d
				best = u
	return best


func _check_game_over() -> void:
	var players_alive := false
	var enemies_alive := false
	for u in units:
		if u.hp > 0:
			if u.team == "player":
				players_alive = true
			else:
				enemies_alive = true
	if not enemies_alive:
		game_over = true
		message_label.text = "🎉 Victoire ! Tous les ennemis sont vaincus."
	elif not players_alive:
		game_over = true
		message_label.text = "💀 Défaite... toutes tes unités sont tombées."
