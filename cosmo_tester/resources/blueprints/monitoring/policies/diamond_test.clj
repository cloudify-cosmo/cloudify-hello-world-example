(let [downstream (changed-state {:init "pending"}
                  (where (state "ok")
                    process-policy-triggers))]
  (where* (fn [event] (.contains (:service event) "{{contains}}"))
    (with :state "ok" downstream)
    (else
      (with :state "pending" downstream))))
