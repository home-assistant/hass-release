cd ../home-assistant
git fetch
git log origin/master...origin/$1 --pretty=format:'- %s (%ae)' --reverse | grep '(#' > '../hass-release/notes.txt'
