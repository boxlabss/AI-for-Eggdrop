# grok.tcl
#
# Eggdrop script for Grok with XaiChatApi.py Flask server.

package require http
package require json

# Configuration
set ai(link) "http://127.0.0.1:5000/chat"        ;# Flask API endpoint for Grok
set ai(secured) "0"                               ;# HTTPS disabled (0 = HTTP, 1 = HTTPS)
set ai(rate_limit) 5                              ;# Seconds between user requests per channel
set ai(max_msg_length) 400                        ;# Max IRC message length
set ai(max_request_age) 3600                      ;# Clean request records older than 1 hour
array set ai_last_request {}                      ;# Track last request time per user-channel

# Enable HTTPS if configured
if {$ai(secured) == 1} {
    package require tls
    http::register https 443 [list ::tls::socket -autoservername true]
}

# Bind to public messages
bind pubm - * ai:botnickTalk
setudef flag grok

proc ai:botnickTalk {nick uhost handle target args} {
    # Process public messages starting with bot nickname 'Grok'
    global botnick ai ai_last_request
    set message [join [lrange $args 0 end] " "]
    
    # Only process messages starting with botnick
    if {![string match -nocase "$botnick *" $message]} {
        return
    }
    
    # Check if Grok is enabled for the channel
    if {![channel get $target grok]} {
        putlog "Grok not enabled for channel $target"
        putquick "PRIVMSG $target :Grok is not enabled for this channel."
        return
    }
    
    # Extract query after botnick
    set message [string trim [string range $message [string length $botnick] end]]
    if {$message == ""} {
        putquick "PRIVMSG $target :Please provide a message!"
        return
    }
    
    # Rate-limit per user-channel
    set user_key "$nick:$target"
    set current_time [clock seconds]
    if {[info exists ai_last_request($user_key)] && [expr {$current_time - $ai_last_request($user_key)}] < $ai(rate_limit)} {
        putquick "PRIVMSG $target :Please wait a few seconds before asking again!"
        return
    }
    set ai_last_request($user_key) $current_time
    
    # Clean old request records to prevent memory growth
    ai:clean_old_requests $current_time
    
    # Send request to Flask API
    set encodedMessage [::http::formatQuery message $message nick $nick]
    set url "$ai(link)?$encodedMessage"
    putlog "Sending request to $url"
    
    # Async HTTP request with retries
    set attempts 0
    set max_attempts 3
    while {$attempts < $max_attempts} {
        incr attempts
        if {[catch {
            ::http::geturl $url -timeout 30000 -command [list ai:callback $target $nick] -headers {Accept application/json}
        } error]} {
            putlog "HTTP error (attempt $attempts/$max_attempts): $error"
            if {$attempts < $max_attempts} {
                putlog "Retrying after [expr {1000 * (2 ** ($attempts - 1))}]ms"
                after [expr {1000 * (2 ** ($attempts - 1))}]
                continue
            }
            putquick "PRIVMSG $target :Sorry, I couldn't connect to Grok! (Error: $error, Attempt: $attempts/$max_attempts)"
            return
        }
        return
    }
}

proc ai:clean_old_requests {current_time} {
    # Remove request records older than max_request_age to prevent memory growth
    global ai ai_last_request
    foreach key [array names ai_last_request] {
        if {[expr {$current_time - $ai_last_request($key)}] > $ai(max_request_age)} {
            unset ai_last_request($key)
        }
    }
}

proc ai:callback {target nick token} {
    # Handle async HTTP response from Flask API
    global ai
    set status [::http::status $token]
    set response [::http::data $token]
    set http_code [::http::ncode $token]
    ::http::cleanup $token
    
    # Check HTTP status
    if {$status != "ok" || $http_code != 200} {
        putlog "HTTP error: status=$status, code=$http_code, response=$response"
        putquick "PRIVMSG $target :Sorry, I couldn't connect to Grok! (Status: $status, Code: $http_code)"
        return
    }
    
    # Parse JSON response
    if {[catch {set json_data [::json::json2dict $response]} error]} {
        putlog "JSON parse error: $error, response=$response"
        putquick "PRIVMSG $target :Sorry, I couldn't parse the Grok response!"
        return
    }
    
    # Extract and display reply
    if {[dict exists $json_data reply]} {
        set output [dict get $json_data reply]
        ai:displayMessage $output $target $nick
    } else {
        set fallback [dict exists $json_data fallback] ? [dict get $json_data fallback] : "Sorry, no response from Grok!"
        putlog "JSON missing reply key: $response"
        putquick "PRIVMSG $target :$fallback"
    }
}

proc ai:displayMessage {output target nick} {
    # Display response in IRC, splitting long messages to respect max_msg_length
    global ai
    set output [string map {\\\" "\"" \\n "\n" \\t "\t"} $output]
    foreach line [split $output "\n"] {
        if {$line == ""} {
            continue
        }
        while {[string length $line] > $ai(max_msg_length)} {
            set chunk [string range $line 0 [expr {$ai(max_msg_length) - 1}]]
            set last_space [string last " " $chunk]
            if {$last_space > 0} {
                set chunk [string range $line 0 [expr {$last_space - 1}]]
                set line [string range $line $last_space end]
            } else {
                set line [string range $line $ai(max_msg_length) end]
            }
            putquick "PRIVMSG $target :$chunk"
        }
        if {$line != ""} {
            putquick "PRIVMSG $target :$line"
        }
    }
}

putlog "grok.tcl loaded"